# INIT-103 Phase 3 Proposal: Infisical Runtime Secret Store

## Binding Sources
- `.pipeline/research.md` - Phase 1 evidence for Infisical OSS, the
  Kubernetes Operator, `InfisicalSecret`, Universal Auth, SOPS boundaries,
  local-first proof requirements, and version availability.
- `.pipeline/synthesis.md` - Phase 2 D1 through D11 decisions.
- `../init-102-gitops-substrate/.pipeline/proposal.md` - binding Flux
  substrate: raw Git source, `source-controller` + `kustomize-controller`
  only, SOPS+age bootstrap-only, and no Helm controller.
- `../init-102-gitops-substrate/.pipeline/implementation.md` - INIT-103
  handoff: Infisical installs under `gitops/channels/local/`, runtime
  application secrets must not enter SOPS, and `InfisicalSecret` is the
  runtime contract.
- `DECISIONS.md` D8 - local-as-first-deployment, self-managed k3s everywhere,
  bootstrap-only SOPS, Infisical runtime secrets, and Vultr-locked remote.
- `~/.claude3/projects/-home-nes-projects-server-manager/memory/environment-agnostic-stack.md`
  - local and remote run the same stack shape with channel-specific endpoint
  and provider config.
- `~/ai/conventions/no-backwards-compatibility.md` - no compatibility shims,
  transitional aliases, dual support, or fallbacks.

This proposal operationalizes D1 through D11 for INIT-103. The binding result
is a real Infisical OSS server, local in-cluster database dependencies,
Infisical Kubernetes Operator, Universal Auth bootstrap, one
`InfisicalSecret` sample, and a harness proof that the Operator syncs a secret
from Infisical into Kubernetes in the `local` k3d channel.

## 1. Scope Summary
INIT-103 ships the runtime secret-management layer for the Phase 5 local
channel. It commits raw Kubernetes manifests under
`gitops/channels/local/infisical/` for the Infisical server and Operator,
extends channel YAML with a strict `infisical` block, extends the pinned local
toolchain with Helm and the Infisical CLI, adds one SOPS-encrypted bootstrap
Secret for server-root configuration, adds a host-side idempotent identity
bootstrap script that creates the local project, sample secret, Machine
Identity, and Operator Universal Auth Secret, and proves the end-to-end
runtime contract by reconciling `InfisicalSecret/infisical-local-sample` into
`Secret/infisical-local-sample`.

INIT-103 does not ship object storage, cert-manager, DNS, TLS, ingress,
Crossplane, container delivery, CI/CD, application data-plane Postgres,
backups, application workloads, Authentik, access policy, tenant isolation, or
observability. Those belong to INIT-104 through INIT-117, listed explicitly in
Section 12. Infisical's UI remains cluster-internal through a `ClusterIP`
Service only; no public exposure, TLS, user access model, rotation policy, or
backup/restore process is introduced here.

## 2. Module/File Surface
The INIT-102 baseline already contains `gitops/`, `gitops/channels/local/`,
`gitops/bootstrap/`, Flux source manifests, channel schemas, local bring-up,
tool installation, and the bootstrap validation harness. INIT-103 modifies
that surface and adds an Infisical subtree under the local channel.

| Path | Type | Purpose | New vs modified |
|---|---|---|---|
| `.pipeline/proposal.md` | proposal | Binding Phase 3 design for INIT-103. | Modified; replaces stale INIT-102 text. |
| `gitops/channels/local/kustomization.yaml` | Kubernetes manifest | Adds `infisical/` to the local Flux-reconciled overlay after the bootstrap sentinel. | Modified. |
| `gitops/channels/local/infisical/` | directory | Local channel Infisical root containing server, operator, and sample reconciliation manifests. | New. |
| `gitops/channels/local/infisical/kustomization.yaml` | Kubernetes manifest | Kustomize entrypoint for namespace, server, operator, and sample resources. | New. |
| `gitops/channels/local/infisical/namespace.yaml` | Kubernetes manifest | Creates `Namespace/infisical-system` for server, data dependencies, Operator, and UA Secret. | New. |
| `gitops/channels/local/infisical/server/` | directory | Infisical server manifest set, including chart-rendered Postgres and Redis. | New. |
| `gitops/channels/local/infisical/server/kustomization.yaml` | Kubernetes manifest | Packages the rendered server output. | New. |
| `gitops/channels/local/infisical/server/render-values.yaml` | Helm values | Render input for `infisical-standalone` chart v1.8.0. | New. |
| `gitops/channels/local/infisical/server/rendered/` | directory | Committed raw output from `helm template` for the Infisical application chart. | New. |
| `gitops/channels/local/infisical/server/rendered/infisical-standalone-1.8.0.yaml` | Kubernetes manifest | Raw rendered Infisical app, PostgreSQL, Redis, ServiceAccount, migration job/RBAC, Services, StatefulSets, and PVC templates as produced by Helm. | New. |
| `gitops/channels/local/infisical/operator/` | directory | Infisical Kubernetes Operator rendered manifest set. | New. |
| `gitops/channels/local/infisical/operator/kustomization.yaml` | Kubernetes manifest | Packages the raw rendered Operator chart output. | New. |
| `gitops/channels/local/infisical/operator/render-values.yaml` | Helm values | Render input for `secrets-operator` chart v0.10.32. | New. |
| `gitops/channels/local/infisical/operator/rendered/secrets-operator-0.10.32.yaml` | Kubernetes manifest | Raw rendered Operator chart output, including all six CRDs, RBAC, ServiceAccount, Deployment, and metrics Service. | New. |
| `gitops/channels/local/infisical/sample/` | directory | End-to-end sample `InfisicalSecret` proof. | New. |
| `gitops/channels/local/infisical/sample/kustomization.yaml` | Kubernetes manifest | Packages sample namespace and sample `InfisicalSecret`. | New. |
| `gitops/channels/local/infisical/sample/namespace.yaml` | Kubernetes manifest | Creates `Namespace/infisical-sample` for the proof target Secret. | New. |
| `gitops/channels/local/infisical/sample/infisical-local-sample.yaml` | Kubernetes manifest | `InfisicalSecret/infisical-local-sample` syncing `/sample` from the local project into a managed Kubernetes Secret. | New. |
| `gitops/bootstrap/infisical-server-bootstrap.enc.yaml` | Kubernetes manifest | SOPS-encrypted `Secret/infisical-server-bootstrap` for server-root bootstrap configuration. | New. |
| `.sops.yaml` | SOPS config | Keeps bootstrap-only encrypted YAML rule; no path wildcard expansion beyond existing regex. | Unmodified unless formatting changes are needed. |
| `infra/channels/local.yaml` | channel YAML | Adds the required concrete `infisical` block for `k3d-local`. | Modified. |
| `infra/channels/dev.yaml` | channel YAML | Keeps `infisical` omitted for `vultr-vms` until remote Flux/Infisical is scoped. | Unmodified. |
| `infra/channels/fixtures/local-child.yaml` | channel fixture | Adds inherited or concrete `infisical` expectations for local child resolution. | Modified. |
| `infra/schemas/platform-channel.schema.json` | JSON Schema | Adds top-level `infisical` definition and requires it when `cluster.target == "k3d-local"`. | Modified. |
| `infra/schemas/platform-channel-resolved.schema.json` | JSON Schema | Adds resolved `infisical` definition and the same local requirement. | Modified. |
| `infra/scripts/resolve_platform_channel.py` | script | Resolves and validates inherited `infisical` channel fields without shims. | Modified. |
| `infra/scripts/validate_platform_channels.py` | script | Includes `infisical` schema fixtures in channel validation. | Modified. |
| `infra/scripts/install-cluster-tools.sh` | script | Adds idempotent version-checked installs for Helm v3.20.2 and Infisical CLI v0.43.78. | Modified. |
| `infra/scripts/render-infisical-manifests.sh` | script | Renders pinned upstream Helm charts into committed raw YAML and verifies render invariants. | New. |
| `infra/scripts/bootstrap-infisical-identity.sh` | script | Host-side idempotent post-server bootstrap for admin, project, environment, sample secret, Machine Identity, and UA Secret. | New. |
| `infra/scripts/bring-up-local-channel.sh` | script | Runs Infisical identity bootstrap after Flux applies the server and before waiting on sample reconciliation. | Modified. |
| `infra/scripts/lint-sops-boundary.py` | script | Extends encrypted-file allowlist to exactly one new Infisical server bootstrap file and keeps runtime-secret guards. | Modified. |
| `infra/tests/validate_platform_bootstrap.sh` | harness | Calls the Infisical runtime harness when `--cluster` is used. | Modified. |
| `infra/tests/validate_infisical_runtime.sh` | harness | Live-cluster assertions for server readiness, PVCs, Operator, UA Secret, sample CR condition, target Secret, and idempotency. | New. |
| `infra/tests/test_platform_channel_infisical_schema.py` | test | Schema/resolver tests for required local block and optional Vultr block. | New. |
| `infra/tests/test_sops_boundary_infisical.py` | test | Positive and negative tests for the new SOPS allowlist and forbidden runtime-secret keys. | New. |
| `gitops/README.md` | documentation | Documents runtime-secret ownership, Infisical subtree, render workflow, rollback, and INIT-104 conventions. | Modified. |
| `infra/README.md` | documentation | Documents toolchain pins, bootstrap ordering, local proof commands, and INIT-104 handoff. | Modified. |

### Directory Layout
The local channel layout is:

```text
gitops/channels/local/infisical/
  kustomization.yaml
  namespace.yaml
  server/
    kustomization.yaml
    render-values.yaml
    rendered/
      infisical-standalone-1.8.0.yaml
  operator/
    kustomization.yaml
    render-values.yaml
    rendered/
      secrets-operator-0.10.32.yaml
  sample/
    kustomization.yaml
    namespace.yaml
    infisical-local-sample.yaml
```

The split is intentional. `server/rendered/` and `operator/rendered/` are raw
Helm output. `sample/` is an authored contract proof. The root
`infisical/kustomization.yaml` is the only path added to
`gitops/channels/local/kustomization.yaml`.

## 3. Schema Changes
D7/D8 require a strict additive top-level `infisical` block in both channel
schemas. `schema_version` remains `1`. The block is required for
`cluster.target == "k3d-local"` and optional for `cluster.target ==
"vultr-vms"`.

The exact JSON Schema addition is:

```json
{
  "properties": {
    "infisical": {
      "$ref": "#/$defs/infisical"
    }
  },
  "allOf": [
    {
      "if": {
        "properties": {
          "cluster": {
            "properties": {
              "target": {
                "const": "k3d-local"
              }
            },
            "required": ["target"]
          }
        },
        "required": ["cluster"]
      },
      "then": {
        "required": ["gitops", "infisical"]
      }
    },
    {
      "if": {
        "properties": {
          "cluster": {
            "properties": {
              "target": {
                "const": "vultr-vms"
              }
            },
            "required": ["target"]
          }
        },
        "required": ["cluster"]
      },
      "then": {}
    }
  ],
  "$defs": {
    "infisical": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "server_url",
        "project_id",
        "environment",
        "secrets_path",
        "auth_method",
        "universal_auth_secret_name",
        "universal_auth_secret_namespace",
        "operator_namespace",
        "resync_interval"
      ],
      "properties": {
        "server_url": {
          "type": "string",
          "pattern": "^https?://[^\\s/$.?#].[^\\s]*$"
        },
        "project_id": {
          "type": "string",
          "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]{2,127}$"
        },
        "environment": {
          "type": "string",
          "pattern": "^[a-z0-9][a-z0-9-]*$"
        },
        "secrets_path": {
          "type": "string",
          "pattern": "^/([A-Za-z0-9._-]+(/|$))*$",
          "default": "/"
        },
        "auth_method": {
          "type": "string",
          "enum": ["universal-auth"]
        },
        "universal_auth_secret_name": {
          "type": "string",
          "pattern": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
          "default": "infisical-operator-auth"
        },
        "universal_auth_secret_namespace": {
          "type": "string",
          "pattern": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
          "default": "infisical-system"
        },
        "operator_namespace": {
          "type": "string",
          "pattern": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
          "default": "infisical-system"
        },
        "resync_interval": {
          "type": "string",
          "pattern": "^[1-9][0-9]*(s|m|h)$",
          "default": "60s"
        }
      }
    }
  }
}
```

The local channel concrete block is:

```yaml
infisical:
  server_url: http://infisical.infisical-system.svc.cluster.local:8080
  project_id: platform-local
  environment: local
  secrets_path: /sample
  auth_method: universal-auth
  universal_auth_secret_name: infisical-operator-auth
  universal_auth_secret_namespace: infisical-system
  operator_namespace: infisical-system
  resync_interval: 60s
```

Per-target behavior:

- `k3d-local`: `infisical` is required. The local channel self-hosts
  Infisical in the local k3d cluster and points the Operator at the
  cluster-internal Service URL.
- `vultr-vms`: `infisical` is optional in INIT-103. Remote remains Vultr
  locked and will self-host or share an Infisical instance only when a later
  remote GitOps slice installs Flux and Infisical on that target. Managed
  third-party Infisical is not introduced as the default remote path.
- Child channels inherit `infisical` the same way they inherit other additive
  channel blocks. There is no compatibility alias such as `env_slug`,
  `project_slug`, or `service_token_secret_name`.

## 4. Helm-Render-To-Raw Pipeline
D1 and D2 bind Helm as a render-time tool only. INIT-103 never installs
`helm-controller`, never commits `HelmRelease`, and never asks Flux to fetch a
chart.

Pins:

| Dependency | Pin | Source |
|---|---:|---|
| Helm CLI | `v3.20.2` | Latest Helm v3 release observed 2026-04-26. |
| Infisical server chart | `infisical-standalone` `1.8.0` | Cloudsmith Helm index created 2026-04-07. |
| Infisical Operator chart | `secrets-operator` `0.10.32` | Cloudsmith Helm index created 2026-04-17. |
| Infisical server image | `infisical/infisical:v0.151.0` | D11 synthesis binding. |
| Infisical Operator image | `infisical/kubernetes-operator:v0.10.32` | Operator chart appVersion/image pin. |
| PostgreSQL rendered image | `mirror.gcr.io/bitnamilegacy/postgresql:16.2.0-debian-11-r16` | `infisical-standalone` v1.8.0 bundled PostgreSQL chart. |
| Redis rendered image | `mirror.gcr.io/bitnamilegacy/redis:7.2.4-debian-11-r18` | `infisical-standalone` v1.8.0 bundled Redis chart. |
| Infisical CLI | `v0.43.78` | Latest CLI release observed 2026-04-26. |

`infra/scripts/render-infisical-manifests.sh` is the single render entrypoint:

```bash
helm repo add infisical-helm-charts \
  https://dl.cloudsmith.io/public/infisical/helm-charts/helm/charts/
helm repo update infisical-helm-charts

helm template infisical \
  infisical-helm-charts/infisical-standalone \
  --version 1.8.0 \
  --namespace infisical-system \
  --values gitops/channels/local/infisical/server/render-values.yaml \
  > gitops/channels/local/infisical/server/rendered/infisical-standalone-1.8.0.yaml

helm template infisical-operator \
  infisical-helm-charts/secrets-operator \
  --version 0.10.32 \
  --namespace infisical-system \
  --values gitops/channels/local/infisical/operator/render-values.yaml \
  > gitops/channels/local/infisical/operator/rendered/secrets-operator-0.10.32.yaml
```

Server render values:

```yaml
infisical:
  replicaCount: 1
  image:
    repository: infisical/infisical
    tag: v0.151.0
    pullPolicy: IfNotPresent
  kubeSecretRef: infisical-server-bootstrap
  service:
    type: ClusterIP
  resources:
    requests:
      cpu: 350m
    limits:
      memory: 1000Mi
  autoBootstrap:
    enabled: false
ingress:
  enabled: false
postgresql:
  enabled: true
  fullnameOverride: postgresql
  image:
    registry: mirror.gcr.io
    repository: bitnamilegacy/postgresql
    tag: 16.2.0-debian-11-r16
  primary:
    persistence:
      size: 8Gi
redis:
  enabled: true
  fullnameOverride: redis
  image:
    registry: mirror.gcr.io
    repository: bitnamilegacy/redis
    tag: 7.2.4-debian-11-r18
  master:
    persistence:
      size: 8Gi
ingress-nginx:
  enabled: false
```

Operator render values:

```yaml
hostAPI: http://infisical.infisical-system.svc.cluster.local:8080
controllerManager:
  replicas: 1
  manager:
    image:
      repository: infisical/kubernetes-operator
      tag: v0.10.32
    resources:
      requests:
        cpu: 10m
        memory: 64Mi
      limits:
        cpu: 500m
        memory: 128Mi
scopedNamespaces: []
scopedRBAC: false
installCRDs: true
telemetry:
  serviceMonitor:
    enabled: false
```

Idempotency contract:

- Re-running `render-infisical-manifests.sh` with the same pins produces the
  same files byte-for-byte except for Helm comments that are stripped by the
  script.
- The script writes to a temporary file, normalizes with `kubectl neat` if
  available or a local YAML normalizer if not, then atomically replaces the
  committed target.
- The script fails if rendered manifests contain `helm.sh/chart`,
  `meta.helm.sh/release-name`, `meta.helm.sh/release-namespace`, `app.kubernetes.io/managed-by: Helm`,
  `HelmRelease`, `OCIRepository`, or unpinned image tags.
- The script fails if the rendered image set differs from the table above.
- Upgrade is a deliberate edit to the version constants, render values, and
  rendered YAML in the same commit. No runtime chart fetch is possible.

## 5. Bootstrap Secret-Zero Flow
D4 and D5 split bootstrap into server-root secrets and post-startup Operator
identity credentials.

SOPS allowlist extension:

```python
ALLOWED_ENCRYPTED_FILES = {
    Path("gitops/bootstrap/sops-sentinel.enc.yaml"),
    Path("gitops/bootstrap/infisical-server-bootstrap.enc.yaml"),
}
```

The exact new encrypted file is:

```text
gitops/bootstrap/infisical-server-bootstrap.enc.yaml
```

It reconciles as:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: infisical-server-bootstrap
  namespace: infisical-system
type: Opaque
stringData:
  ENCRYPTION_KEY: <sops-encrypted>
  AUTH_SECRET: <sops-encrypted>
  SITE_URL: http://infisical.infisical-system.svc.cluster.local:8080
  DB_CONNECTION_URI: <sops-encrypted>
  REDIS_URL: <sops-encrypted>
  INFISICAL_AUTO_BOOTSTRAP_EMAIL: <sops-encrypted>
  INFISICAL_AUTO_BOOTSTRAP_PASSWORD: <sops-encrypted>
```

The linter still rejects every encrypted file outside the allowlist and still
rejects runtime-secret-shaped keys. Inside
`infisical-server-bootstrap.enc.yaml`, only the seven server-root keys above
are allowed. The two `INFISICAL_AUTO_BOOTSTRAP_*` keys are root-admin
bootstrap credentials consumed by `bootstrap-infisical-identity.sh`; they are
not used by the Helm chart auto-bootstrap job, which remains disabled.
Operator UA credentials, service tokens, Discord tokens,
application DB passwords, MinIO credentials, Vultr Object Storage credentials,
and API keys are rejected everywhere in SOPS.

The Operator UA credential is generated after the Infisical server is running:

- Script: `infra/scripts/bootstrap-infisical-identity.sh`
- Execution point: host-side step invoked by `bring-up-local-channel.sh` after
  Flux reports the local Kustomization Ready and after
  `Deployment/infisical` is Available.
- Manual operator step: if bring-up is interrupted after server readiness,
  run `bash infra/scripts/bootstrap-infisical-identity.sh --channel local`
  from the repo root; it performs the same idempotent reconciliation and then
  returns control to the harness.
- Output: direct `kubectl apply` of `Secret/infisical-operator-auth` in
  `infisical-system`, with keys `clientId` and `clientSecret`.
- Git boundary: the UA Secret is never committed and never SOPS-encrypted.

Bootstrap script contract:

1. Resolve channel `local` and read `infisical.*` fields from the resolved
   channel JSON.
2. Wait for `Deployment/infisical`, `StatefulSet/postgresql`, and
   `StatefulSet/redis-master` in `infisical-system`.
3. Port-forward the Infisical Service to localhost for CLI/API operations.
4. Read `INFISICAL_AUTO_BOOTSTRAP_EMAIL` and
   `INFISICAL_AUTO_BOOTSTRAP_PASSWORD` from
   `Secret/infisical-server-bootstrap`, without printing values.
5. Create the first admin user if no users exist.
6. Create or find organization `platform`.
7. Create or find project id `platform-local` with slug `local`.
8. Create or find environment slug `local`.
9. Create or update secret `/sample/INFISICAL_SAMPLE_KEY` to
   `infisical-local-ready`.
10. Create or find Machine Identity `local-operator`.
11. Enable Universal Auth on that identity with project `platform-local`,
    environment `local`, path `/sample`, and read-only secret access.
12. Create or rotate the client secret only when the Kubernetes Secret is
    missing or explicitly passed `--rotate`.
13. Apply `Secret/infisical-operator-auth` with non-empty `clientId` and
    `clientSecret`.

Idempotency and recovery:

- If the server is already bootstrapped and the UA Secret exists, rerun is a
  no-op except for verifying the sample secret value.
- If the server is bootstrapped but the UA Secret is missing, rerun recreates
  only the UA Secret from Infisical.
- If the sample secret is missing or has the wrong value, rerun corrects it.
- If Flux has not applied CRDs yet, the script exits with a clear error and no
  partial write to Git.
- The script never prints `clientSecret`, `ENCRYPTION_KEY`, `AUTH_SECRET`,
  `DB_CONNECTION_URI`, or `REDIS_URL`.

## 6. Infisical Server Install
The local done state includes:

- Infisical application: one replica of `infisical/infisical:v0.151.0`.
- Frontend: bundled in the standalone Infisical image, not a separate
  Deployment.
- PostgreSQL: in-cluster, PVC-backed, chart-rendered, one primary.
- Redis: in-cluster, PVC-backed, standalone master.
- Operator: installed separately per Section 7.
- One `InfisicalSecret` sample and target Kubernetes Secret per Section 10.

PostgreSQL binding:

- Workload: `StatefulSet/postgresql` in `infisical-system`.
- Service: `Service/postgresql` in `infisical-system`.
- Image: `mirror.gcr.io/bitnamilegacy/postgresql:16.2.0-debian-11-r16`.
- PVC: chart default `8Gi`, default k3d storage class `local-path`.
- Scope: Infisical metadata and encrypted secret storage only.
- Anti-scope: INIT-111 application data Postgres, HA, external managed
  database, backup/restore.

Redis binding:

- Workload: `StatefulSet/redis-master` in `infisical-system`.
- Service: `Service/redis-master` in `infisical-system`.
- Image: `mirror.gcr.io/bitnamilegacy/redis:7.2.4-debian-11-r18`.
- PVC: chart default `8Gi`, default k3d storage class `local-path`.
- Required: yes. Infisical OSS self-hosting requires Redis and the server
  receives `REDIS_URL` from `Secret/infisical-server-bootstrap`.
- Anti-scope: external Redis, HA Redis, managed Redis, cache sharing.

Service exposure:

- `Service/infisical` is `ClusterIP`.
- The channel `server_url` points to
  `http://infisical.infisical-system.svc.cluster.local:8080`.
- No Ingress, LoadBalancer, NodePort, public DNS, TLS, or UI publication is
  part of INIT-103.

Resource limits:

- Infisical app requests `350m` CPU and limits memory to `1000Mi`.
- Operator requests `10m` CPU / `64Mi` memory and limits `500m` CPU /
  `128Mi` memory.
- PostgreSQL and Redis keep upstream chart defaults except image tags and
  PVC size pins.

## 7. Operator Install
D2 installs the Infisical Kubernetes Operator through raw committed manifests
rendered from `secrets-operator` chart v0.10.32.

Rendered set:

- `CustomResourceDefinition/infisicalsecrets.secrets.infisical.com`
- `CustomResourceDefinition/infisicalpushsecrets.secrets.infisical.com`
- `CustomResourceDefinition/infisicaldynamicsecrets.secrets.infisical.com`
- `CustomResourceDefinition/clustergenerators.secrets.infisical.com`
- `CustomResourceDefinition/passwords.secrets.infisical.com`
- `CustomResourceDefinition/uuids.secrets.infisical.com`
- Operator `ServiceAccount`, ClusterRole, ClusterRoleBinding, leader-election
  Role/RoleBinding, metrics auth RBAC, Deployment, and metrics Service.

RBAC binding:

- INIT-103 uses the chart default cluster-wide watch:
  `scopedNamespaces: []` and `scopedRBAC: false`.
- The Operator can reconcile namespaced `InfisicalSecret` CRs across the
  cluster, including `infisical-sample`.
- INIT-116 owns scoped namespace delegation and tenant isolation. INIT-103
  does not implement partial scoping or compatibility toggles.

Connectivity:

- Chart-level `hostAPI` is
  `http://infisical.infisical-system.svc.cluster.local:8080`.
- The sample CR also sets `spec.hostAPI` from channel `infisical.server_url`
  so downstream CRs do not depend on the chart default.
- Authentication is Universal Auth only:
  `spec.authentication.universalAuth.credentialsRef.secretName:
  infisical-operator-auth`,
  `secretNamespace: infisical-system`.

## 8. Toolchain Installer
`infra/scripts/install-cluster-tools.sh` remains the single local toolchain
entrypoint. INIT-103 extends it with Helm and Infisical CLI.

Pinned tools:

| Tool | Version | Linux amd64 asset | SHA256 |
|---|---:|---|---|
| Helm | `v3.20.2` | `helm-v3.20.2-linux-amd64.tar.gz` | `258e830a9e613c8a7a302d6059b4bb3b9758f2f3e1bb8ea0d707ce10a9a72fea` |
| Infisical CLI | `v0.43.78` | `cli_0.43.78_linux_amd64.tar.gz` | `4cba7e88befff7fab44bc45bf9a0d8fe307d85748267a4c76c25deb72f38be74` |

Install behavior:

- `--check` prints OK/MISSING/MISMATCH for `helm` and `infisical`, just like
  existing `k3d`, `flux`, `sops`, and `age` checks.
- `--install` downloads only missing or mismatched tools.
- Each download is checksum-verified before moving into `~/.local/bin`.
- Version detection uses `helm version --short` and `infisical --version`.
- Only linux-amd64 installs are supported for the new tools in INIT-103,
  matching existing Flux/SOPS constraints.
- Helm is required for re-rendering and validation. It is not installed into
  the cluster and not used during Flux reconciliation.

## 9. Slice Decomposition

### SLICE-103.01 - Toolchain Pins
Files:

- `infra/scripts/install-cluster-tools.sh`
- `infra/README.md`
- `infra/tests/validate_platform_bootstrap.sh`

Acceptance:

- `bash infra/scripts/install-cluster-tools.sh --check --no-color` checks
  `helm v3.20.2` and `infisical v0.43.78`.
- `bash infra/scripts/install-cluster-tools.sh --install --no-color` installs
  both tools idempotently when missing.
- Re-running `--install` does not redownload matching versions.
- Mismatched local versions produce a nonzero `--check`.

Anti-scope:

- No cluster resources.
- No Infisical server or Operator manifests.
- No package-manager based install path.

Dependencies:

- INIT-102 toolchain installer.

### SLICE-103.02 - Infisical Server Raw Manifests
Files:

- `gitops/channels/local/kustomization.yaml`
- `gitops/channels/local/infisical/kustomization.yaml`
- `gitops/channels/local/infisical/namespace.yaml`
- `gitops/channels/local/infisical/server/kustomization.yaml`
- `gitops/channels/local/infisical/server/render-values.yaml`
- `gitops/channels/local/infisical/server/rendered/infisical-standalone-1.8.0.yaml`
- `infra/scripts/render-infisical-manifests.sh`

Acceptance:

- `bash infra/scripts/render-infisical-manifests.sh --check` confirms
  rendered output is current.
- `kubectl kustomize gitops/channels/local/infisical/server` succeeds.
- Rendered image set contains only pinned images listed in Section 4.
- No `HelmRelease`, `OCIRepository`, or Helm ownership annotations appear.

Anti-scope:

- No Operator.
- No UA bootstrap.
- No sample `InfisicalSecret`.
- No public exposure.

Dependencies:

- SLICE-103.01.

### SLICE-103.03 - Infisical Operator Raw Manifests
Files:

- `gitops/channels/local/infisical/operator/kustomization.yaml`
- `gitops/channels/local/infisical/operator/render-values.yaml`
- `gitops/channels/local/infisical/operator/rendered/secrets-operator-0.10.32.yaml`
- `infra/scripts/render-infisical-manifests.sh`

Acceptance:

- `kubectl kustomize gitops/channels/local/infisical/operator` succeeds.
- The rendered set includes all six CRDs named in Section 7.
- Operator image is exactly `infisical/kubernetes-operator:v0.10.32`.
- Operator RBAC remains chart default cluster-wide watch.

Anti-scope:

- No tenant isolation or scoped RBAC.
- No Kubernetes Auth.
- No `InfisicalPushSecret` or dynamic secret proof.

Dependencies:

- SLICE-103.01.

### SLICE-103.04 - Bootstrap Boundary And Identity Script
Files:

- `gitops/bootstrap/infisical-server-bootstrap.enc.yaml`
- `gitops/channels/local/infisical/server/kustomization.yaml`
- `infra/scripts/lint-sops-boundary.py`
- `infra/scripts/bootstrap-infisical-identity.sh`
- `infra/scripts/bring-up-local-channel.sh`
- `infra/tests/test_sops_boundary_infisical.py`

Acceptance:

- `python infra/scripts/lint-sops-boundary.py` passes with exactly two
  encrypted files.
- A fixture encrypted file outside `gitops/bootstrap/` fails the lint.
- A fixture containing Operator UA keys in SOPS fails the lint.
- `bootstrap-infisical-identity.sh --help` documents idempotency and
  `--rotate`.
- Re-running the bootstrap script after first success leaves the UA Secret and
  sample secret valid.

Anti-scope:

- No credential rotation policy beyond explicit `--rotate`.
- No INIT-115 access policy.
- No storage or application runtime secrets in SOPS.

Dependencies:

- SLICE-103.02.

### SLICE-103.05 - Channel Schema And Sample InfisicalSecret
Files:

- `infra/schemas/platform-channel.schema.json`
- `infra/schemas/platform-channel-resolved.schema.json`
- `infra/channels/local.yaml`
- `infra/channels/fixtures/local-child.yaml`
- `infra/scripts/resolve_platform_channel.py`
- `infra/scripts/validate_platform_channels.py`
- `infra/tests/test_platform_channel_infisical_schema.py`
- `gitops/channels/local/infisical/sample/kustomization.yaml`
- `gitops/channels/local/infisical/sample/namespace.yaml`
- `gitops/channels/local/infisical/sample/infisical-local-sample.yaml`

Acceptance:

- `python infra/scripts/validate_platform_channels.py` passes.
- Local channel without `infisical` fails schema validation.
- Dev `vultr-vms` channel without `infisical` remains valid.
- `kubectl kustomize gitops/channels/local/infisical/sample` succeeds.
- Sample CR references `projectId: platform-local`, `envSlug: local`,
  `secretsPath: /sample`, and UA Secret in `infisical-system`.

Anti-scope:

- No service-token auth.
- No Kubernetes Auth.
- No project slug alias.
- No downstream INIT-104 storage CR.

Dependencies:

- SLICE-103.03 and SLICE-103.04.

### SLICE-103.06 - Local Runtime Harness
Files:

- `infra/tests/validate_infisical_runtime.sh`
- `infra/tests/validate_platform_bootstrap.sh`
- `infra/README.md`

Acceptance:

- `bash infra/tests/validate_platform_bootstrap.sh` passes render/schema
  checks without a cluster.
- `bash infra/tests/validate_platform_bootstrap.sh --cluster` brings up local
  k3d, installs Flux, applies Infisical, bootstraps identity, and passes all
  Section 10 assertions.
- AUD-001/SC-006: the cluster harness waits for the upstream
  `InfisicalSecret` sync condition from Operator chart v0.10.32, not a
  guessed `Ready` or `Reconciled` condition:

  ```bash
  kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$TARGET_NS" wait \
    --for=condition=secrets.infisical.com/ReadyToSyncSecrets=True \
    --timeout=180s \
    infisicalsecret/infisical-local-sample
  ```

  Here `TARGET_NS=infisical-sample`. The 180s timeout gives three local
  `resync_interval: 60s` cycles while staying bounded below the 300s
  infrastructure readiness waits.
- AUD-001/SC-006: after the condition wait, the harness verifies
  `Secret/infisical-local-sample` in `infisical-sample`; key
  `INFISICAL_SAMPLE_KEY` must decode to `infisical-local-ready`.
- Running the cluster harness twice proves idempotency.
- Deleting the Infisical Pod and waiting proves the Postgres PVC remains
  Bound and data-backed sample sync still succeeds.

Anti-scope:

- No CI wiring.
- No remote Vultr harness.
- No backup/restore proof.

Dependencies:

- SLICE-103.02 through SLICE-103.05.

### SLICE-103.07 - Documentation And INIT-104 Handoff
Files:

- `gitops/README.md`
- `infra/README.md`
- `.pipeline/implementation.md`

Acceptance:

- Docs describe the render workflow, SOPS boundary, bootstrap order,
  rollback order, and local proof command.
- Docs state INIT-104 object-storage project/path/key conventions exactly as
  Section 13.
- `.pipeline/implementation.md` records completed slices, verification
  commands, and the INIT-104 handoff.

Anti-scope:

- No INIT-104 implementation.
- No object-storage secrets.
- No MinIO manifests.

Dependencies:

- SLICE-103.06.

## 10. Local-As-First-Deployment Proof
The live local proof runs after INIT-102's substrate harness has succeeded.
The exact assertions are:

1. Infisical server Pod Ready:
   `kubectl -n infisical-system wait deployment/infisical
   --for=condition=Available --timeout=300s`.
2. PostgreSQL Ready:
   `kubectl -n infisical-system rollout status statefulset/postgresql
   --timeout=300s`.
3. PostgreSQL PVC Bound:
   the PVC owned by `StatefulSet/postgresql` reports `status.phase=Bound` and
   `spec.storageClassName=local-path`.
4. PostgreSQL persistence:
   deleting the Postgres Pod recreates it against the same PVC name, and the
   bootstrap script still finds the existing project/sample secret.
5. Redis Ready:
   `kubectl -n infisical-system rollout status statefulset/redis-master
   --timeout=300s`.
6. Redis PVC Bound:
   the Redis master PVC reports `status.phase=Bound` and
   `spec.storageClassName=local-path`.
7. Operator Ready:
   `kubectl -n infisical-system wait deployment/infisical-operator-controller-manager
   --for=condition=Available --timeout=300s`.
8. UA Secret present:
   `Secret/infisical-operator-auth` exists in `infisical-system` and contains
   non-empty `clientId` and `clientSecret` keys; values are never printed.
9. Sample CR reconciled (AUD-001/SC-006):
   the canonical successful-sync condition for the pinned Operator chart
   v0.10.32 is `secrets.infisical.com/ReadyToSyncSecrets=True`, from
   `SetReadyToSyncSecretsConditions` in
   https://github.com/Infisical/kubernetes-operator/blob/infisical-k8-operator/v0.10.32/internal/services/infisicalsecret/conditions.go.
   This is the binding contract for the audit checklist's generic "Reconciled"
   semantics — the pinned Operator does not write a `Reconciled` condition,
   so `secrets.infisical.com/ReadyToSyncSecrets=True` is the audited substrate.
   The CRD schema allows condition `observedGeneration`, but the v0.10.32
   controller does not set it on this condition, so the harness does not
   assert `observedGeneration == metadata.generation`.

   ```bash
   kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$TARGET_NS" wait \
     --for=condition=secrets.infisical.com/ReadyToSyncSecrets=True \
     --timeout=180s \
     infisicalsecret/infisical-local-sample
   ```

   `TARGET_NS` is `infisical-sample`. The 180s timeout gives three
   `resync_interval: 60s` cycles and prevents an unbounded local proof.
10. Target Secret exists:
    `Secret/infisical-local-sample` in `infisical-sample` exists after the
    condition wait.
11. Target Secret value:
    key `INFISICAL_SAMPLE_KEY` decodes to `infisical-local-ready`.
12. Re-bring-up idempotency:
    a second `bring-up-local-channel.sh local` run reports already-up cluster,
    re-seeds Flux, re-runs the identity bootstrap as a no-op, and all
    assertions remain green.

The harness does not duplicate INIT-102 assertions. It starts after Flux
source and root Kustomization readiness are already established.

## 11. Risk And Supported-Surface Track
Current-state risk reduced:

- Today there is no runtime secret manager in the live platform substrate.
- SOPS is intentionally bootstrap-only, so runtime secrets currently have no
  approved home.
- Without INIT-103, downstream INIT-104, INIT-111, and INIT-113 would either
  hardcode secrets, place runtime credentials in ConfigMaps, or violate the
  SOPS boundary.

Blast radius:

- New namespace `infisical-system`.
- Infisical application Pod.
- PostgreSQL StatefulSet and 8Gi PVC.
- Redis StatefulSet and 8Gi PVC.
- Cluster-scoped Operator CRDs and RBAC.
- Operator write authority over Kubernetes Secrets.
- Load-bearing host-side secret-zero step for UA credentials.

Migration path:

- None. This is the first install of runtime secret management.
- No legacy secret-store compatibility, aliases, or dual paths are introduced.

Rollback path:

1. Delete consumer CRs first:
   `kubectl delete infisicalsecret -A --all`.
2. Delete managed sample Secret if it remains:
   `kubectl -n infisical-sample delete secret infisical-local-sample --ignore-not-found`.
3. Delete the local channel Infisical subtree:
   `kubectl delete -k gitops/channels/local/infisical/`.
4. Delete CRDs only after confirming no `InfisicalSecret`,
   `InfisicalPushSecret`, or `InfisicalDynamicSecret` resources remain.
5. Delete PVCs only when data loss is accepted:
   `kubectl -n infisical-system delete pvc -l app.kubernetes.io/instance=infisical`.

Observability:

- Server logs:
  `kubectl -n infisical-system logs deployment/infisical`.
- Operator logs:
  `kubectl -n infisical-system logs deployment/infisical-operator-controller-manager`.
- CR status:
  `kubectl -n infisical-sample get infisicalsecret infisical-local-sample -o yaml`.
- Target Secret:
  `kubectl -n infisical-sample get secret infisical-local-sample`.
- PVC state:
  `kubectl -n infisical-system get pvc`.

Risk areas for the 3x gate:

- Secret-zero sequencing: the host-side script is load-bearing and must be
  truly idempotent across partial bootstrap states.
- Chart/render pin drift: server image D11 is pinned to `v0.151.0` while the
  current upstream chart defaults to newer images; the render script must make
  the chosen pins explicit and reviewable.
- Operator RBAC breadth: INIT-103 accepts cluster-wide watch/write as the
  chart default, leaving namespace scoping to INIT-116.

## 12. Anti-Scope
Binding anti-scope by successor INIT:

- INIT-104: object storage, MinIO local, Vultr Object Storage remote, S3
  buckets, bucket lifecycle, and storage credential `InfisicalSecret` CRs.
- INIT-105: cert-manager, TLS issuers, DNS automation, local CA, ACME, and
  any Infisical TLS endpoint.
- INIT-106: Crossplane, provider configuration, claims, compositions, and
  app-cluster provisioning.
- INIT-107: cluster security baseline, Pod Security admission policy,
  network policy baseline, node hardening, and default-deny rules.
- INIT-108: container delivery, image registry choice, image build/push, and
  GHCR or replacement registry setup.
- INIT-109: CI/CD, Buildkite agents, pipelines, image promotion, and CI
  secrets.
- INIT-110: ingress, public routing, Infisical UI exposure, external DNS, and
  HTTP(S) publication.
- INIT-111: application data plane, application Postgres, database users,
  schemas, migrations, and app DB credentials.
- INIT-112: backup and restore, Infisical Postgres backup, PVC snapshots,
  disaster recovery, and retention policy.
- INIT-113: app workloads, API Deployment, Discord daemon Deployment,
  workload `InfisicalSecret` CRs beyond the INIT-103 sample, and auto-reload
  annotations.
- INIT-114: Authentik, OIDC, user SSO, OPAL/Cedar, Pomerium, and app auth.
- INIT-115: Infisical access policy, admin model, credential rotation,
  break-glass, age key rotation, and Operator credential lifecycle.
- INIT-116: tenant isolation, namespace delegation, scoped Operator RBAC,
  per-tenant secret paths, and multi-tenant Infisical project policy.
- INIT-117: observability stack, Prometheus/Grafana/Alertmanager, Loki,
  OpenTelemetry, Flux notifications, alerts, and dashboards.

Additional anti-scope:

- No `HelmRelease`, `helm-controller`, or runtime Helm reconciliation.
- No `OCIRepository` or object-storage-backed GitOps source.
- No remote `dev` Flux/Infisical install in this INIT.
- No `InfisicalPushSecret`, `InfisicalDynamicSecret`, `ClusterGenerator`,
  `Password`, or `UUID` exercise; only CRDs are installed.
- No runtime secrets in SOPS.
- No service-token auth and no Kubernetes Auth.
- No compatibility aliases, deprecated field names, or migration shims.

## 13. INIT-104 Handoff
INIT-104 consumes Infisical through the contract below. INIT-103 documents the
interface but does not create INIT-104 resources.

Storage project convention:

- Project: `platform-storage`
- Environment: channel `infisical.environment` (`local` for k3d-local)
- Secrets path: `/object-storage`
- Auth: Universal Auth, either reusing the INIT-103 bootstrap UA credential
  or creating an INIT-104-owned Machine Identity scoped to `platform-storage`.
  INIT-104 makes that scoping decision.
- Operator namespace: channel `infisical.operator_namespace`, default
  `infisical-system`.
- Consumer namespace: owned by INIT-104, expected `minio-system` for local.

Local MinIO keys:

```text
/object-storage/MINIO_ROOT_USER
/object-storage/MINIO_ROOT_PASSWORD
```

Remote Vultr Object Storage keys:

```text
/object-storage/VULTR_OS_ACCESS_KEY
/object-storage/VULTR_OS_SECRET_KEY
```

INIT-104 must author its own `InfisicalSecret` CRs in its application
namespace. It must not add MinIO or Vultr Object Storage credentials to
`gitops/bootstrap/` or to any SOPS-encrypted file.

## 14. D-Record Binding Confirmation
- D1 `D-INFISICAL-INSTALL`: server installed as raw committed manifests
  under `gitops/channels/local/infisical/server/`, rendered from
  `infisical-standalone` v1.8.0 by Helm template.
- D2 `D-OPERATOR-INSTALL`: Operator installed as raw committed manifests
  under `gitops/channels/local/infisical/operator/`, rendered from
  `secrets-operator` v0.10.32 with all six CRDs.
- D3 `D-OPERATOR-AUTH`: Universal Auth only; sample CR references
  `Secret/infisical-operator-auth` and explicit project/env/path scope.
- D4 `D-SECRET-ZERO`: server-root config is SOPS-encrypted; UA credentials
  are generated post-server-startup and applied directly with kubectl.
- D5 `D-SOPS-BOUNDARY-EXTEND`: exactly one new encrypted file is allowlisted:
  `gitops/bootstrap/infisical-server-bootstrap.enc.yaml`.
- D6 `D-INFISICAL-COMPONENTS`: done state includes server, bundled frontend,
  PostgreSQL, Redis, Operator, CRDs, one sample CR, and one target Secret.
- D7 `D-DATA-PLANE`: PostgreSQL and Redis are in-cluster, PVC-backed,
  8Gi each, and distinct from INIT-111's application data plane.
- D8 `D-CHANNEL-SCHEMA-EXT`: strict `infisical` block added to source and
  resolved schemas; required for `k3d-local`, optional for `vultr-vms`.
- D9 `D-LOCAL-CONTRACT`: harness proves server Ready, PVC Bound/persistent,
  Operator Ready, sample CR
  `secrets.infisical.com/ReadyToSyncSecrets=True`, target Secret value, and
  idempotency (AUD-001/SC-006 closure preserves the binding).
- D10 `D-INIT-104-HANDOFF`: object-storage conventions are bound to
  `platform-storage`, `/object-storage`, UA auth, and per-target key names.
- D11 `D-VERSION-PINS`: Helm, charts, images, Infisical CLI, Postgres, and
  Redis are pinned; render script verifies no floating image or chart input.
