# INIT-104 Phase 3 Proposal: S3-Compatible Object Storage

## Binding Sources
- `.pipeline/research.md` - Phase 1 evidence for MinIO packaging, bucket
  creation, S3-compatible clients, Vultr Object Storage, Infisical runtime
  credential flow, channel schema extension, and local proof requirements.
- `.pipeline/synthesis.md` - Phase 2 decision records D1 through D12.
- `../init-103-infisical-runtime-secrets/.pipeline/proposal.md` - binding
  Infisical substrate, `InfisicalSecret` CR shape, Universal Auth pattern,
  bootstrap-only SOPS boundary, and INIT-104 handoff.
- `../init-103-infisical-runtime-secrets/.pipeline/implementation.md` -
  concrete handoff: local Infisical endpoint, local environment, Operator UA
  Secret shape, and `/object-storage/<channel>/...` storage path convention.
- `../init-102-gitops-substrate/.pipeline/proposal.md` - binding GitOps
  substrate: raw Kustomize manifests under `gitops/channels/local`, Flux
  source plus kustomize controllers only, no helm-controller, no runtime chart
  reconciliation, and local bring-up through scripts.
- `DECISIONS.md` D8 - local-as-first-deployment, self-managed k3s on k3d and
  Vultr VMs, SOPS+age bootstrap-only, Infisical runtime secrets, channel
  templates, Vultr-locked remote, and MinIO surviving only as local S3.
- `~/ai/conventions/no-backwards-compatibility.md` - no compatibility shims,
  deprecated aliases, dual field names, transition layers, or fallbacks.

This proposal operationalizes INIT-104 synthesis D1 through D12. The binding
result is a raw Kustomize-managed local MinIO install, storage credentials
synced from Infisical, an idempotent bucket-creation Job, a provider-neutral
S3 env var contract, a Vultr Object Storage remote contract, channel schema
support for object storage, pinned `mc` tooling, and a local harness proof
that PUT/GET round trips work against a real S3-compatible endpoint.

## 1. Scope Summary
INIT-104 ships the S3-compatible object-storage layer for the local channel
and the channel contract for the future remote Vultr channel. Locally it adds
`gitops/channels/local/object-storage/` with raw Kubernetes manifests for
`Namespace/minio-system`, an `InfisicalSecret` that materializes
`Secret/minio-root`, a single-node MinIO `Deployment`, `Service`, `PVC`, and a
one-shot idempotent bucket Job that creates `humility-local-sample`. It also
extends channel schemas with `object_storage`, extends the local toolchain
with a pinned `mc` binary, adds `bootstrap-infisical-storage.sh` to seed
sample storage credentials into Infisical, adds a provider-neutral S3
round-trip script, and extends the live local harness so local is a real
deployment rather than a render-only check.

Anti-scope is explicit. INIT-104 does not ship cert-manager, DNS, TLS,
Ingress, MinIO Console exposure, Crossplane, cluster security baseline,
container delivery, CI/CD, application data plane, backup, app workloads,
auth, storage access policy, tenant isolation, or observability. Those are
owned by INIT-105 through INIT-117. It also does not provision Vultr Object
Storage subscriptions or buckets, install remote Flux or remote Infisical,
create app-scoped S3 credentials, rotate credentials, introduce HelmRelease
or helm-controller, use the MinIO Operator, or create any backwards-compatible
schema aliases.

## 2. Module/File Surface
INIT-104 modifies the existing INIT-102/INIT-103 substrate. The local GitOps
overlay already reconciles `gitops/channels/local/kustomization.yaml`; this
proposal adds one object-storage subtree under that overlay.

| Path | Type | Purpose | New vs modified |
|---|---|---|---|
| `.pipeline/proposal.md` | proposal | Binding Phase 3 design for INIT-104. | Modified; replaces stale INIT-103 text. |
| `gitops/channels/local/kustomization.yaml` | Kubernetes manifest | Adds `object-storage/` to the local Flux-reconciled overlay after Infisical resources. | Modified. |
| `gitops/channels/local/object-storage/` | directory | Local channel object-storage root. | New. |
| `gitops/channels/local/object-storage/kustomization.yaml` | Kubernetes manifest | Kustomize entrypoint for namespace, credentials, MinIO, and bucket job. | New. |
| `gitops/channels/local/object-storage/namespace.yaml` | Kubernetes manifest | Creates `Namespace/minio-system`. | New. |
| `gitops/channels/local/object-storage/infisical/` | directory | Storage credential sync manifests. | New. |
| `gitops/channels/local/object-storage/infisical/kustomization.yaml` | Kubernetes manifest | Packages the local storage `InfisicalSecret`. | New. |
| `gitops/channels/local/object-storage/infisical/minio-root-infisicalsecret.yaml` | Kubernetes manifest | Syncs `/object-storage/local/` from project `platform-storage` to `Secret/minio-root`. | New. |
| `gitops/channels/local/object-storage/minio/` | directory | Raw MinIO workload manifest set. | New. |
| `gitops/channels/local/object-storage/minio/kustomization.yaml` | Kubernetes manifest | Packages ServiceAccount, PVC, Deployment, and Service. | New. |
| `gitops/channels/local/object-storage/minio/serviceaccount.yaml` | Kubernetes manifest | Dedicated `ServiceAccount/minio`; no Kubernetes API RBAC granted. | New. |
| `gitops/channels/local/object-storage/minio/pvc.yaml` | Kubernetes manifest | `PersistentVolumeClaim/minio-data`, `10Gi`, `local-path`. | New. |
| `gitops/channels/local/object-storage/minio/deployment.yaml` | Kubernetes manifest | Single-replica MinIO API Deployment using pinned image and Infisical-synced env. | New. |
| `gitops/channels/local/object-storage/minio/service.yaml` | Kubernetes manifest | `ClusterIP` Service `minio` exposing S3 API port `9000` only. | New. |
| `gitops/channels/local/object-storage/buckets/` | directory | Bucket bootstrap manifests. | New. |
| `gitops/channels/local/object-storage/buckets/kustomization.yaml` | Kubernetes manifest | Packages ServiceAccount and one-shot bucket creation Job. | New. |
| `gitops/channels/local/object-storage/buckets/serviceaccount.yaml` | Kubernetes manifest | Dedicated `ServiceAccount/minio-bucket-bootstrap`; no Kubernetes API RBAC granted. | New. |
| `gitops/channels/local/object-storage/buckets/create-sample-bucket-job.yaml` | Kubernetes manifest | Runs pinned `quay.io/minio/mc` and `mc mb --ignore-existing` for `humility-local-sample`. | New. |
| `infra/channels/local.yaml` | channel YAML | Adds required concrete `object_storage` block for `k3d-local`. | Modified. |
| `infra/channels/dev.yaml` | channel YAML | Adds optional aspirational Vultr Object Storage block with operator-supplied endpoint shape, no install resources. | Modified. |
| `infra/channels/fixtures/local-child.yaml` | channel fixture | Exercises inheritance of `object_storage` from local parent. | Modified. |
| `infra/channels/fixtures/dev-child.yaml` | channel fixture | Exercises optional Vultr object-storage inheritance when present. | Modified if needed by tests. |
| `infra/schemas/platform-channel.schema.json` | JSON Schema | Adds strict top-level `object_storage` definition and local target requirement. | Modified. |
| `infra/schemas/platform-channel-resolved.schema.json` | JSON Schema | Adds resolved `object_storage` definition and local target requirement. | Modified. |
| `infra/scripts/resolve_platform_channel.py` | script | Resolves inherited `object_storage` values and computes Vultr endpoint when omitted from `region`. | Modified. |
| `infra/scripts/validate_platform_channels.py` | script | Validates local and optional Vultr object-storage schema cases. | Modified. |
| `infra/scripts/install-cluster-tools.sh` | script | Adds pinned host `mc` version check and install path. | Modified. |
| `infra/scripts/bootstrap-infisical-storage.sh` | script | Idempotently seeds `platform-storage`, `/object-storage/local/`, and MinIO sample credentials while reusing INIT-103's Operator UA Secret. | New. |
| `infra/scripts/bring-up-local-channel.sh` | script | Runs storage bootstrap after INIT-103 Infisical identity bootstrap and before Flux waits on object-storage reconciliation. | Modified. |
| `infra/scripts/sample-s3-roundtrip.py` | script | Reads `S3_*` env vars, performs PUT, GET, content check, and DELETE using an S3-compatible SDK. | New. |
| `infra/scripts/object-storage-requirements.txt` | pinned dependency file | Pins the Python SDK dependencies used by the sample round-trip script. | New. |
| `infra/tests/validate_platform_bootstrap.sh` | harness | Calls the object-storage harness under `--cluster`. | Modified. |
| `infra/tests/validate_object_storage_local.sh` | harness | Live local assertions for MinIO, PVC, InfisicalSecret, Secret keys, bucket, SDK round trip, and idempotency. | New. |
| `infra/tests/test_platform_channel_object_storage.py` | test | Schema/resolver tests for local required block, Vultr optional block, endpoint resolution, and inheritance. | New. |
| `infra/tests/test_object_storage_manifests.py` | test | Static checks for raw manifests, pinned images, no HelmRelease, no MinIO Operator, probes, resources, and Secret refs. | New. |
| `gitops/README.md` | documentation | Documents local object-storage GitOps subtree, MinIO rollback, and no Console/Ingress boundary. | Modified. |
| `infra/README.md` | documentation | Documents toolchain pin, storage bootstrap order, local proof command, and Vultr operator handoff. | Modified. |

### Directory Layout
The local channel layout is:

```text
gitops/channels/local/object-storage/
  kustomization.yaml
  namespace.yaml
  infisical/
    kustomization.yaml
    minio-root-infisicalsecret.yaml
  minio/
    kustomization.yaml
    serviceaccount.yaml
    pvc.yaml
    deployment.yaml
    service.yaml
  buckets/
    kustomization.yaml
    serviceaccount.yaml
    create-sample-bucket-job.yaml
```

`object-storage/kustomization.yaml` applies resources in dependency order:
namespace first, then `infisical/`, then `minio/`, then `buckets/`. The
ordering does not replace readiness checks; it keeps ownership legible while
the MinIO probes, the `InfisicalSecret` condition, and the bucket Job command
handle actual readiness.

## 3. Schema Changes
D7 adds a strict top-level `object_storage` block to both source and resolved
channel schemas. `schema_version` remains `1` because this is additive and the
remote `vultr-vms` channel remains valid without remote install resources.

The block is required when `cluster.target == "k3d-local"`. It is optional
when `cluster.target == "vultr-vms"` because INIT-104 does not install remote
Flux, remote Infisical, or Vultr Object Storage resources. If present on a
Vultr channel, it must be `provider: "vultr-object-storage"` and must either
provide an endpoint or allow the resolver to compute
`https://<region>1.vultrobjects.com` from `cluster.vultr_vms.region`.

The local concrete block in `infra/channels/local.yaml` is:

```yaml
object_storage:
  provider: minio
  endpoint: http://minio.minio-system.svc.cluster.local:9000
  region: us-east-1
  bucket: humility-local-sample
  credentials_secret_name: minio-root
  credentials_secret_namespace: minio-system
  infisical_project: platform-storage
  infisical_path: /object-storage/local/
```

The optional Vultr block in `infra/channels/dev.yaml` is:

```yaml
object_storage:
  provider: vultr-object-storage
  endpoint: https://ewr1.vultrobjects.com
  region: ewr
  bucket: humility-dev-sample
  credentials_secret_name: vultr-object-storage
  credentials_secret_namespace: app-runtime
  infisical_project: platform-storage
  infisical_path: /object-storage/dev/
```

The exact JSON Schema addition is:

```json
{
  "properties": { "object_storage": { "$ref": "#/$defs/objectStorage" } },
  "allOf": [
    {
      "if": {
        "properties": {
          "cluster": { "properties": { "target": { "const": "k3d-local" } }, "required": ["target"] }
        },
        "required": ["cluster"]
      },
      "then": {
        "required": ["gitops", "infisical", "object_storage"],
        "properties": {
          "object_storage": {
            "properties": {
              "provider": { "const": "minio" },
              "endpoint": { "const": "http://minio.minio-system.svc.cluster.local:9000" },
              "region": { "const": "us-east-1" },
              "bucket": { "const": "humility-local-sample" },
              "credentials_secret_name": { "const": "minio-root" },
              "credentials_secret_namespace": { "const": "minio-system" },
              "infisical_project": { "const": "platform-storage" },
              "infisical_path": { "const": "/object-storage/local/" }
            }
          }
        }
      }
    },
    {
      "if": {
        "properties": {
          "cluster": { "properties": { "target": { "const": "vultr-vms" } }, "required": ["target"] }
        },
        "required": ["cluster"]
      },
      "then": {
        "properties": {
          "object_storage": {
            "properties": {
              "provider": { "const": "vultr-object-storage" },
              "endpoint": { "pattern": "^https://[a-z]{3}1\\.vultrobjects\\.com$" },
              "region": { "$ref": "#/$defs/region" },
              "infisical_project": { "const": "platform-storage" },
              "infisical_path": { "pattern": "^/object-storage/[a-z0-9][a-z0-9-]*/$" }
            }
          }
        }
      }
    }
  ],
  "$defs": {
    "objectStorage": {
      "type": "object",
      "additionalProperties": false,
      "required": ["provider", "endpoint", "region", "bucket", "credentials_secret_name", "credentials_secret_namespace", "infisical_project", "infisical_path"],
      "properties": {
        "provider": { "type": "string", "enum": ["minio", "vultr-object-storage"] },
        "endpoint": { "type": "string", "pattern": "^https?://[A-Za-z0-9.-]+(?::[0-9]{1,5})?$" },
        "region": { "type": "string", "pattern": "^[a-z0-9-]+$" },
        "bucket": { "type": "string", "minLength": 3, "maxLength": 63, "pattern": "^[a-z0-9][a-z0-9.-]*[a-z0-9]$" },
        "credentials_secret_name": { "type": "string", "pattern": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$" },
        "credentials_secret_namespace": { "type": "string", "pattern": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$" },
        "infisical_project": { "type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]{2,127}$" },
        "infisical_path": { "type": "string", "pattern": "^/object-storage/[a-z0-9][a-z0-9-]*/$" }
      }
    }
  }
}
```

Required versus optional:

- Source schema: `object_storage` is optional at the top level so child and
  remote plan channels can exist before inherited resolution or remote GitOps
  install.
- Resolved schema: `object_storage` is required for `k3d-local` because local
  is the done state for INIT-104.
- `vultr-vms`: `object_storage` is optional in INIT-104. If present, all fields
  inside the block are required and validated.
- Child channels inherit `object_storage` exactly like `gitops` and
  `infisical`. No aliases such as `s3`, `storage`, `endpoint_url`,
  `secret_namespace`, or provider-specific app fields are accepted.

Resolver behavior:

- Preserve explicit source values.
- Inherit `object_storage` from parent before schema-validating resolved JSON.
- For `provider: vultr-object-storage`, if implementation chooses to allow
  endpoint omission in source YAML, the resolver must compute
  `https://<cluster.vultr_vms.region>1.vultrobjects.com` before resolved schema
  validation. The resolved schema still requires `endpoint`.
- For `provider: minio`, endpoint resolution is not dynamic; it is exactly the
  in-cluster Service URL.

## 4. MinIO Install
D1 and D2 bind INIT-104 to raw single-node MinIO manifests. No Helm chart, no
MinIO Operator, no Tenant CRD, no AdminJob, no HelmRelease, and no
helm-controller are introduced.

Version pins:

| Artifact | Pin | Digest or checksum |
|---|---|---|
| MinIO server image | `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z` | manifest digest `sha256:5fa6d6eb3204468b7898bbdbf7dd2169217831cdce8f85833bf89f2d21020e41` |
| MinIO `mc` image | `quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z` | manifest digest `sha256:7a740f5dbc9c1ea04512a86eb27714b3ed025dd1825aa958aaae0c2298b54398` |
| Host `mc` binary | `mc.RELEASE.2025-08-13T08-35-41Z` | `01f866e9c5f9b87c2b09116fa5d7c06695b106242d829a8bb32990c00312e891` |

The MinIO server and `mc` tags are both fixed `RELEASE.<timestamp>` tags from
the MinIO release family. They do not use `latest`. The `mc` tag is not the
same timestamp as the server tag because `quay.io/minio/mc` does not publish
the server's `RELEASE.2025-09-07T16-13-09Z` tag; the selected `mc` tag is the
latest verified `mc` release available in the official binary archive and
Quay image registry during proposal verification.

Concrete local resources:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: minio-system
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: minio
  namespace: minio-system
automountServiceAccountToken: false
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: minio-data
  namespace: minio-system
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-path
  resources:
    requests:
      storage: 10Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: minio
  namespace: minio-system
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app.kubernetes.io/name: minio
      app.kubernetes.io/part-of: object-storage
  template:
    metadata:
      labels:
        app.kubernetes.io/name: minio
        app.kubernetes.io/part-of: object-storage
    spec:
      serviceAccountName: minio
      containers:
        - name: minio
          image: quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z
          imagePullPolicy: IfNotPresent
          args:
            - server
            - /data
            - --address
            - :9000
          env:
            - name: MINIO_ROOT_USER
              valueFrom:
                secretKeyRef:
                  name: minio-root
                  key: MINIO_ROOT_USER
            - name: MINIO_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: minio-root
                  key: MINIO_ROOT_PASSWORD
            - name: MINIO_BROWSER
              value: "off"
          ports:
            - name: s3
              containerPort: 9000
          readinessProbe:
            httpGet:
              path: /minio/health/ready
              port: s3
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 2
            failureThreshold: 24
          livenessProbe:
            httpGet:
              path: /minio/health/live
              port: s3
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 2
            failureThreshold: 6
          resources:
            requests:
              cpu: 250m
              memory: 512Mi
            limits:
              cpu: "1"
              memory: 1Gi
          volumeMounts:
            - name: data
              mountPath: /data
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: minio-data
---
apiVersion: v1
kind: Service
metadata:
  name: minio
  namespace: minio-system
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: minio
    app.kubernetes.io/part-of: object-storage
  ports:
    - name: s3
      port: 9000
      targetPort: s3
```

RBAC minimum:

- MinIO server receives a dedicated ServiceAccount.
- `automountServiceAccountToken: false` is set because MinIO does not need the
  Kubernetes API.
- No Role or RoleBinding is created for the MinIO server.
- The bucket Job receives a separate ServiceAccount, also without API token
  automount and without Role/RoleBinding.

Console contract:

- The MinIO Console is not deployed in INIT-104.
- `MINIO_BROWSER=off` disables the browser UI.
- The Service exposes only port `9000`.
- No port `9001`, Ingress, Pomerium route, DNS name, or TLS certificate is
  created.

Secret source:

- The Deployment consumes `Secret/minio-root` in namespace `minio-system`.
- `Secret/minio-root` is owned by `InfisicalSecret/minio-root`.
- The committed GitOps manifests never contain `MINIO_ROOT_USER` or
  `MINIO_ROOT_PASSWORD` literal values.
- SOPS remains bootstrap-only; no storage credential is added to
  `gitops/bootstrap/`.

## 5. Bucket Creation
D3 binds initial bucket creation to a post-readiness Kubernetes Job using the
official MinIO `mc` client image. The Job creates exactly one sample bucket in
INIT-104: `humility-local-sample`.

Concrete Job:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: minio-bucket-bootstrap
  namespace: minio-system
automountServiceAccountToken: false
---
apiVersion: batch/v1
kind: Job
metadata:
  name: create-sample-bucket
  namespace: minio-system
spec:
  backoffLimit: 12
  template:
    metadata:
      labels:
        app.kubernetes.io/name: create-sample-bucket
        app.kubernetes.io/part-of: object-storage
    spec:
      restartPolicy: OnFailure
      serviceAccountName: minio-bucket-bootstrap
      containers:
        - name: mc
          image: quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z
          imagePullPolicy: IfNotPresent
          env:
            - name: MINIO_ROOT_USER
              valueFrom:
                secretKeyRef:
                  name: minio-root
                  key: MINIO_ROOT_USER
            - name: MINIO_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: minio-root
                  key: MINIO_ROOT_PASSWORD
            - name: S3_ENDPOINT
              value: http://minio.minio-system.svc.cluster.local:9000
            - name: S3_REGION
              value: us-east-1
            - name: S3_BUCKET
              value: humility-local-sample
          command:
            - /bin/sh
            - -ceu
            - |
              mc alias set local "${S3_ENDPOINT}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"
              mc ready local
              mc mb --ignore-existing --region "${S3_REGION}" "local/${S3_BUCKET}"
```

Lifecycle:

- This is a one-shot `Job`, not a CronJob.
- The Job has a stable name and no TTL. Once complete, Flux re-apply leaves it
  complete and idempotent.
- If a developer intentionally needs to recreate buckets after manual deletion,
  they delete `Job/create-sample-bucket`; Flux or `kubectl apply -k` recreates
  it.
- `mc mb --ignore-existing` is the idempotency primitive. Re-running the Job
  against an existing bucket succeeds.
- The bucket Job is not an init container in the MinIO Pod; bucket creation is
  not tied to server boot.
- The bucket Job is not the MinIO Operator `AdminJob`, because INIT-104 does
  not install the Operator.

Bucket naming:

- Local sample bucket: `humility-local-sample`.
- Future channel sample buckets follow `humility-<channel>-sample`.
- Bucket names must be 3 to 63 characters, lowercase, DNS-compatible, and
  valid for both MinIO and Vultr Object Storage.
- INIT-104 creates only the local sample bucket. App buckets and backup
  buckets are successor work.

## 6. Infisical Credential Flow
D4 and D5 bind storage credentials to Infisical. INIT-104 does not use SOPS,
hardcoded literals, or Kubernetes Secrets committed to Git for MinIO root
credentials.

Local credential source:

- Infisical project: `platform-storage`
- Environment: `local`
- Path: `/object-storage/local/`
- Keys:
  - `MINIO_ROOT_USER`
  - `MINIO_ROOT_PASSWORD`
- Target Kubernetes Secret: `Secret/minio-root`
- Target namespace: `minio-system`
- Key casing in Kubernetes matches Infisical key casing exactly.

Operator Universal Auth reuse (AUDIT-001):

- INIT-104 does not bootstrap a separate Universal Auth credential, Machine
  Identity, or Kubernetes Secret for storage.
- The storage `InfisicalSecret` reuses INIT-103's
  `Secret/infisical-operator-auth` in namespace `infisical-system`.
- The same `clientId` and `clientSecret` keys created by INIT-103 are referenced
  by the new storage `InfisicalSecret`; `bootstrap-infisical-storage.sh` never
  writes a second UA Secret.
- Cross-namespace reference is intentional: the `InfisicalSecret` lives in
  `minio-system`, while
  `spec.authentication.universalAuth.credentialsRef.secretNamespace` points at
  `infisical-system`.
- Storage access is granted to the INIT-103 Operator identity for
  `platform-storage`, environment `local`, path `/object-storage/local/`; no
  INIT-104-specific UA credential is created.

Concrete local `InfisicalSecret`:

```yaml
apiVersion: secrets.infisical.com/v1alpha1
kind: InfisicalSecret
metadata:
  name: minio-root
  namespace: minio-system
spec:
  hostAPI: http://infisical.infisical-system.svc.cluster.local:8080
  authentication:
    universalAuth:
      credentialsRef:
        secretName: infisical-operator-auth
        secretNamespace: infisical-system
      secretsScope:
        projectSlug: platform-storage
        envSlug: local
        secretsPath: /object-storage/local/
        recursive: false
  syncConfig:
    resyncInterval: 60s
  managedSecretReference:
    secretName: minio-root
    secretNamespace: minio-system
    secretType: Opaque
    creationPolicy: Owner
    template:
      includeAllSecrets: true
```

`bootstrap-infisical-storage.sh`:

- Runs after INIT-103 `bootstrap-infisical-identity.sh` proves the Infisical
  server, local environment, and Operator path are usable.
- Reads channel data from `resolve_platform_channel.py --channel local`.
- Creates or finds project `platform-storage`.
- Creates or finds environment `local`.
- Creates or finds folder `/object-storage/local/`.
- Seeds `MINIO_ROOT_USER` on first run. The bound sample username is
  `humility-local-minio`.
- Seeds `MINIO_ROOT_PASSWORD` on first run with at least 32 bytes of
  cryptographically strong random material, base64url-encoded without
  newlines.
- Leaves existing `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` unchanged on
  subsequent runs.
- Verifies INIT-103's `Secret/infisical-operator-auth` exists in
  `infisical-system` with `clientId` and `clientSecret`.
- Grants the INIT-103 Operator identity access to `platform-storage` and the
  `local` environment for the `/object-storage/local/` path.
- Does not create a storage-specific Machine Identity, Universal Auth client, or
  `infisical-storage-operator-auth` Secret.
- Does not rotate the reused Operator UA Secret; MinIO root credential rotation
  is not implemented in INIT-104.

Credential rotation:

- Deferred to INIT-115.
- INIT-104 does not rotate `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, Vultr OS
  access keys, or app scoped credentials.
- INIT-104 only provides an idempotent initial seed for local proof.

## 7. Same-S3-SDK Contract
D6 binds the provider-neutral application and harness environment contract.
The names below are the only names application-facing code should consume:

```text
S3_ENDPOINT
S3_ACCESS_KEY_ID
S3_SECRET_ACCESS_KEY
S3_REGION
S3_BUCKET
```

Local source Secret mapping:

| Consumer env var | Local Secret/key | Value |
|---|---|---|
| `S3_ENDPOINT` | literal or projected config | `http://minio.minio-system.svc.cluster.local:9000` |
| `S3_ACCESS_KEY_ID` | `Secret/minio-root` key `MINIO_ROOT_USER` | Generated by `bootstrap-infisical-storage.sh` |
| `S3_SECRET_ACCESS_KEY` | `Secret/minio-root` key `MINIO_ROOT_PASSWORD` | Generated by `bootstrap-infisical-storage.sh` |
| `S3_REGION` | literal or projected config | `us-east-1` |
| `S3_BUCKET` | literal or projected config | `humility-local-sample` |

The MinIO root Secret keeps provider-native key names because the MinIO server
requires them. Demo and future workload manifests alias those provider-native
keys into the generic `S3_*` names at the container env boundary. No app code
reads `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `VULTR_OS_ACCESS_KEY`, or
`VULTR_OS_SECRET_KEY` directly.

`infra/scripts/sample-s3-roundtrip.py`:

- Reads exactly the five `S3_*` env vars.
- Uses `boto3`/`botocore` as the S3-compatible SDK.
- Configures Signature V4.
- Uses path-style addressing for local MinIO.
- Uses virtual-host style addressing for Vultr Object Storage when endpoint
  host ends with `.vultrobjects.com`.
- Writes a caller-provided object key or a generated
  `init-104-roundtrip/<uuid>.txt` key.
- PUTs a short body, GETs the object, compares bytes, DELETEs the object, and
  exits nonzero if content differs.

Pinned SDK dependency file:

```text
boto3==1.41.5
botocore==1.41.5
jmespath==1.0.1
python-dateutil==2.9.0.post0
s3transfer==0.15.0
six==1.17.0
urllib3==2.5.0
```

The local harness may run the same script through `kubectl run` or a short
Job that projects env vars from `Secret/minio-root` and literals from channel
resolution. The script is a contract proof, not the future app storage wrapper.
The wrapper lands only when INIT-111, INIT-112, or INIT-113 first needs it.

## 8. Vultr OS Contract
D8 binds the remote provider to Vultr Object Storage. INIT-104 does not
provision the subscription, bucket, remote Flux, or remote `InfisicalSecret`;
it defines the contract that later remote INITs must honor.

Endpoint pattern:

```text
https://<region>1.vultrobjects.com
```

For the current `dev` channel, `cluster.vultr_vms.region` is `ewr`, so the
resolved endpoint is:

```text
https://ewr1.vultrobjects.com
```

Vultr bucket provisioning:

- Operator supplied.
- Created through Vultr dashboard, `vultr-cli`, Vultr API, or a future
  Terraform/OpenTofu resource outside INIT-104.
- INIT-104 does not add `vultr_object_storage` resources under `infra/`.
- INIT-104 does not auto-create remote buckets through the S3 SDK on first
  PUT.

Infisical key convention for Vultr:

```text
/object-storage/<channel>/VULTR_OS_ACCESS_KEY
/object-storage/<channel>/VULTR_OS_SECRET_KEY
```

Future Vultr `InfisicalSecret` target Secret:

- Name: `vultr-object-storage`
- Namespace: consumer namespace chosen by the future remote workload slice,
  proposed as `app-runtime`.
- Keys in target Secret:
  - `VULTR_OS_ACCESS_KEY`
  - `VULTR_OS_SECRET_KEY`
- Consumer manifests alias those keys to `S3_ACCESS_KEY_ID` and
  `S3_SECRET_ACCESS_KEY`.

Per-target endpoint resolution:

- `provider: minio` resolves to the channel's explicit in-cluster Service URL.
- `provider: vultr-object-storage` resolves to the explicit endpoint if given.
- If a source Vultr channel omits endpoint, the resolver computes it from
  `cluster.vultr_vms.region` before writing resolved JSON.
- Resolved JSON always contains `object_storage.endpoint`.
- `region` remains the Vultr three-letter region code for Vultr Object
  Storage, not `us-east-1`.

## 9. Slice Decomposition
INIT-104 is implemented in seven locally executable slices.

### SLICE-104.01 - Object Storage Channel Schema
Files: `infra/schemas/platform-channel.schema.json`,
`infra/schemas/platform-channel-resolved.schema.json`, `infra/channels/local.yaml`,
`infra/channels/dev.yaml`, channel fixtures, `resolve_platform_channel.py`,
`validate_platform_channels.py`, and
`infra/tests/test_platform_channel_object_storage.py`.

ACs: channel validation passes; local resolved JSON contains the exact
Section 3 block; removing local `object_storage` fails; `dev` is valid as
`vultr-vms` and, if present, must use `provider: vultr-object-storage`;
`https://ewr1.vultrobjects.com` resolves from `region: ewr`; child channels
inherit; aliases like `s3`, `endpoint_url`, and `secret_namespace` fail.

Anti-scope: schema v2, app workload config, compatibility aliases.
Dependencies: INIT-102/103 schema patterns.

### SLICE-104.02 - Pinned `mc` Toolchain
Files: `infra/scripts/install-cluster-tools.sh`,
`infra/tests/validate_platform_bootstrap.sh`, `infra/README.md`.

ACs: `--check` reports `mc` at `RELEASE.2025-08-13T08-35-41Z`; `--install`
downloads `mc.RELEASE.2025-08-13T08-35-41Z`, verifies
`01f866e9c5f9b87c2b09116fa5d7c06695b106242d829a8bb32990c00312e891`,
installs to `~/.local/bin/mc`, and is idempotent; AWS CLI is not required;
`--check --no-color` remains machine-parseable.

Anti-scope: package-manager install, floating `mc`, AWS CLI pin.
Dependencies: existing tool installer.

### SLICE-104.03 - Infisical Storage Bootstrap
Files: `infra/scripts/bootstrap-infisical-storage.sh`,
`infra/scripts/bring-up-local-channel.sh`,
`gitops/channels/local/object-storage/infisical/*`,
`infra/tests/test_object_storage_manifests.py`.

ACs: help documents idempotency and secret boundaries; after INIT-103 bootstrap
the script creates or finds `platform-storage`, `local`,
`/object-storage/local/`, `MINIO_ROOT_USER`, and `MINIO_ROOT_PASSWORD`; rerun
leaves MinIO root credentials unchanged; it reuses
`Secret/infisical-operator-auth` from `infisical-system`; the
`InfisicalSecret` renders and targets `Secret/minio-root` in `minio-system`.

Anti-scope: MinIO/Vultr credential rotation, Vultr credential seeding, SOPS
storage credential files.
Dependencies: INIT-103 Infisical server and Operator.

### SLICE-104.04 - Raw MinIO Local Manifests
Files: `gitops/channels/local/kustomization.yaml`,
`gitops/channels/local/object-storage/kustomization.yaml`,
`gitops/channels/local/object-storage/namespace.yaml`,
`gitops/channels/local/object-storage/minio/*`,
`infra/tests/test_object_storage_manifests.py`.

ACs: `kubectl kustomize gitops/channels/local/object-storage` succeeds; no
`HelmRelease`, `OCIRepository`, `Tenant`, `AdminJob`, or Operator CRD renders;
image is `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z`; Deployment is
one replica, `Recreate`, `250m/512Mi` request, `1/1Gi` limit, probes, and
`MINIO_BROWSER=off`; Service exposes only `9000`; PVC is `10Gi local-path`;
ServiceAccount has no token automount or RBAC binding.

Anti-scope: Console Service, Ingress/TLS, HA/distributed MinIO.
Dependencies: SLICE-104.03.

### SLICE-104.05 - Bucket Job
Files: `gitops/channels/local/object-storage/buckets/*`,
`infra/tests/test_object_storage_manifests.py`.

ACs: bucket kustomization renders; Job image is
`quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z`; command contains
`mc alias set`, `mc ready`, and `mc mb --ignore-existing`; it creates only
`humility-local-sample`; Job name is stable, has no TTL, and is not a CronJob;
Job ServiceAccount has no token automount or RBAC binding.

Anti-scope: remote, app, and backup buckets.
Dependencies: SLICE-104.04.

### SLICE-104.06 - S3 Round Trip Script
Files: `infra/scripts/sample-s3-roundtrip.py`,
`infra/scripts/object-storage-requirements.txt`,
`infra/tests/validate_object_storage_local.sh`, `infra/README.md`.

ACs: script fails when any `S3_*` env is missing; performs PUT, GET, byte
compare, and DELETE; local MinIO uses path-style addressing; Vultr uses
virtual-host style for `.vultrobjects.com`; dependency file pins every package.

Anti-scope: reusable app wrapper, upload metadata schema, attachment refs.
Dependencies: SLICE-104.01 and SLICE-104.04.

### SLICE-104.07 - Local Harness And Documentation
Files: `infra/tests/validate_object_storage_local.sh`,
`infra/tests/validate_platform_bootstrap.sh`, `gitops/README.md`,
`infra/README.md`, `.pipeline/implementation.md`.

ACs: static bootstrap validation passes; `--cluster` invokes object-storage
validation after INIT-103; the harness verifies Section 10; two bring-up runs
are idempotent; docs state rollback, observability commands, and anti-scope;
implementation handoff records pins, commands, and residual risks.

Anti-scope: remote harness, CI/CD wiring, CodeRabbit execution.
Dependencies: SLICE-104.01 through SLICE-104.06.

## 10. Local-As-First-Deployment Proof
`infra/tests/validate_object_storage_local.sh` is the binding local proof and
is invoked by `infra/tests/validate_platform_bootstrap.sh --cluster`.

Required assertions:

1. Namespace `minio-system` exists.
2. `PersistentVolumeClaim/minio-data` is `Bound`.
3. `Deployment/minio` is Available and its Pod is Ready.
4. `InfisicalSecret/minio-root` reaches
   `secrets.infisical.com/ReadyToSyncSecrets=True`.
5. `Secret/minio-root` exists with non-empty `MINIO_ROOT_USER` and
   `MINIO_ROOT_PASSWORD`.
6. For SC-007, the harness reads `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`
   from Infisical with `infisical secrets get` without printing values, decodes
   the Kubernetes `Secret/minio-root` keys with
   `kubectl get secret minio-root -n minio-system -o jsonpath=... | base64 -d`,
   and asserts byte equality for each key.
7. `Job/create-sample-bucket` is Complete.
8. `mc ls local/humility-local-sample` succeeds from an in-cluster
   `quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z` client.
9. `sample-s3-roundtrip.py` uses the five `S3_*` env vars to PUT bytes, GET
   bytes, compare content, and DELETE its object.
10. For SC-003, the harness uploads a retained sample object, deletes the MinIO
    Pod with `kubectl delete pod -n minio-system -l app.kubernetes.io/name=minio`,
    waits for the Deployment to recreate a Ready Pod, asserts
    `PersistentVolumeClaim/minio-data` remains `Bound`, confirms
    `mc ls local/humility-local-sample` still sees the bucket, then GETs and
    byte-compares the previously uploaded sample object before deleting it.
11. A second `bring-up-local-channel.sh --channel local` succeeds; Flux
   reconciles cleanly; the Job remains Complete; the bucket still exists; a
   second round trip succeeds.

Failure diagnostics are the MinIO `InfisicalSecret`, target Secret,
Deployment, Pod logs, bucket Job logs, and Flux `Kustomization/humility-local`.

No harness step exposes MinIO outside the cluster. Host-side debug may use a
temporary `kubectl port-forward service/minio 19000:9000`, but the harness
canonical path is in-cluster.

## 11. Risk And Supported-Surface Track
Current-state risk reduced: the platform has no accepted S3-compatible storage
layer, no local provider-neutral target for future attachments/exports/backups,
and no storage credential materialization path in Infisical.

Blast radius added: `Namespace/minio-system`, PVC `minio-data`, one MinIO Pod,
ClusterIP Service `minio:9000`, `InfisicalSecret/minio-root`,
`Secret/minio-root`, one bucket Job, two ServiceAccounts, and host `mc`. INIT-104
reuses the existing INIT-103 `Secret/infisical-operator-auth`; it does not add a
second Operator UA Secret.

Migration path: none. INIT-104 is the first accepted object-storage layer
after the D8 reset; no data or app workload migrates, and no compatibility path
from prior MinIO claim buses or provider-native-only storage is preserved.

Rollback path: remove `object-storage/` from local Kustomization and
reseed/reconcile Flux, or `kubectl delete -k
gitops/channels/local/object-storage`; delete `Job/create-sample-bucket`,
`InfisicalSecret/minio-root`, `Secret/minio-root`, and
PVC `minio-data` only after accepting local data loss. Do not delete
INIT-103's reused `Secret/infisical-operator-auth` as part of INIT-104 rollback.
Remove `object_storage` from channel YAML only in the same rollback commit as
manifests/tests.

Observability: Kubernetes probes are primary; inspect
`deploy,pod,pvc,svc,job,infisicalsecret,secret` in `minio-system`, MinIO logs,
bucket Job logs, and Flux `Kustomization/humility-local`. Metrics, dashboards,
alerts, log aggregation, and SLOs are INIT-117.

Top Phase 4 risk areas:

- Secret bootstrap sequencing: MinIO and the bucket Job depend on the
  Infisical Operator syncing `Secret/minio-root`; bring-up must order the
  storage bootstrap and Flux reconcile clearly.
- Job lifecycle under Flux: a stable one-shot Job is idempotent across
  re-apply, but rerunning after manual bucket deletion requires deleting the
  completed Job.
- Local durability expectation: single-node MinIO on one `local-path` PVC is
  real storage for local proof, not HA object storage or backup.

## 12. Anti-Scope
Binding anti-scope by successor INIT:

- INIT-105: cert-manager, DNS, TLS, local CA, ACME, and certificates. MinIO
  stays HTTP on a ClusterIP Service.
- INIT-106: Crossplane, provider configs, claims, compositions, and Vultr
  Object Storage subscription provisioning.
- INIT-107: cluster security baseline, Pod Security admission, default-deny
  NetworkPolicy, node hardening, and full RBAC policy.
- INIT-108: container delivery, registry choice, image builds, image pushes,
  and promotion.
- INIT-109: CI/CD, Buildkite agents, pipelines, image promotion, and CI
  secrets.
- INIT-110: Ingress, public routing, external DNS, Pomerium, and MinIO Console
  exposure. INIT-104 exposes MinIO through ClusterIP only.
- INIT-111: application data plane, app databases, upload models, S3 wrapper,
  and application write paths.
- INIT-112: backup, restore, PVC snapshots, object replication, retention, and
  disaster recovery.
- INIT-113: app workloads, API Deployment, Discord daemon Deployment, and
  workload-specific `InfisicalSecret` resources.
- INIT-114: Authentik, OIDC, user auth, app auth, and policy decision points.
- INIT-115 (SC-010): access policy, credential rotation, fine-grained bucket policies,
  app-scoped S3 users, break-glass, bucket lifecycle policies, server-side bucket
  encryption, bucket versioning, object lifecycle TTL, and age key rotation.
- INIT-116: tenant isolation, namespace delegation, per-tenant buckets,
  per-tenant secret paths, and scoped Operator RBAC.
- INIT-117: observability stack, metrics, logs, alerts, dashboards, and SLOs.

Additional binding anti-scope:

- No MinIO Operator.
- No MinIO Tenant CRD.
- No Operator AdminJob.
- No community MinIO chart.
- No HelmRelease.
- No helm-controller.
- No OCIRepository or bucket-backed Flux source.
- No MinIO Console Service or Ingress.
- No public MinIO API exposure.
- No remote Flux, remote Infisical, or remote storage reconciliation.
- No Terraform/OpenTofu resources for Vultr Object Storage.
- No provider-native-only abstraction.
- No app credentials, bucket policies, bucket lifecycle policies, server-side
  bucket encryption, bucket versioning, or object lifecycle TTL (SC-010).
- No backwards-compatibility aliases, deprecated fields, dual schema support,
  or transitional adapter layers.

## 13. INIT-105 Handoff
INIT-105 owns cert-manager, DNS, and TLS. INIT-104 leaves these endpoint facts:

- Local MinIO API: `http://minio.minio-system.svc.cluster.local:9000`
- Local Service: `Service/minio`, namespace `minio-system`, port `9000`, name `s3`
- Local Console: not deployed and not exposed
- Local protocol/TLS: plain HTTP inside the cluster, no TLS
- Vultr endpoint pattern: `https://<region>1.vultrobjects.com`
- Current `dev` endpoint: `https://ewr1.vultrobjects.com`
- Vultr TLS: terminated by Vultr Object Storage, not cluster cert-manager

If INIT-105 later adds a MinIO Ingress for a non-production development need,
it must introduce DNS, Certificate, Issuer, Ingress, and TLS Secret in its own
proposal and risk gate. INIT-104 creates no HTTPS endpoint fields, Console
exposure, certificate placeholders, or Ingress stubs.

`InfisicalSecret.spec.hostAPI` for storage remains tied to the channel's
Infisical server URL. If a future remote channel self-hosts Infisical behind
Ingress and TLS, that remote channel's `infisical.server_url` changes under
the remote Infisical/TLS initiative; INIT-104's storage CR pattern does not
need to change.

## 14. D-Record Binding Confirmation
- D1 `D-MINIO-INSTALL`: bound to raw single-node MinIO manifests under
  `gitops/channels/local/object-storage/minio/`; no Helm chart, Operator, or
  Tenant CRD.
- D2 `D-MINIO-COMPONENTS`: bound to MinIO API only on ClusterIP port `9000`;
  Console disabled and not exposed.
- D3 `D-BUCKET-CREATION`: bound to one-shot `quay.io/minio/mc` Job with
  `mc alias set`, `mc ready`, and `mc mb --ignore-existing`.
- D4 `D-CREDENTIAL-FLOW`: bound to `platform-storage`, environment `local`,
  path `/object-storage/local/`, `Secret/minio-root`, and INIT-103 Operator UA
  reuse through `Secret/infisical-operator-auth`.
- D5 `D-INFISICAL-BOOTSTRAP`: bound to new sibling
  `bootstrap-infisical-storage.sh`, invoked after INIT-103 Infisical bootstrap.
- D6 `D-S3-SDK-CONTRACT`: bound to the five `S3_*` env vars and the
  provider-neutral round-trip script.
- D7 `D-CHANNEL-SCHEMA-EXT`: bound to strict top-level `object_storage`,
  required for `k3d-local`, optional and Vultr-shaped for `vultr-vms`.
- D8 `D-VULTR-OS-CONTRACT`: bound to
  `https://<region>1.vultrobjects.com`, buckets owned by INIT-106 (Crossplane Vultr provider — `Bucket` claim) with operator/CLI fallback as break-glass only, and
  `VULTR_OS_*` Infisical keys.
- D9 `D-LOCAL-CONTRACT`: bound to harness assertions for Pod Ready, PVC Bound,
  InfisicalSecret Ready, target Secret keys and Infisical byte equality, bucket
  existence, SDK PUT/GET, delete cleanup, Pod-restart durability, and
  re-bring-up idempotency.
- D10 `D-INIT-105-HANDOFF`: bound to plain local MinIO ClusterIP HTTP and
  Vultr provider-side HTTPS facts for future DNS/TLS work.
- D11 `D-ANTI-SCOPE`: restated in Section 12 with successor INIT ownership and
  explicit exclusions.
- D12 `D-VERSION-PINS`: bound to exact MinIO server, `mc` image, host `mc`
  binary, digest, and checksum pins; AWS CLI remains optional.
