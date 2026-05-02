# Infrastructure

Authoritative operator documentation for the Humility deployment substrate.

## Overview

`infra/` contains the completed Phase 5 control-cluster substrate:
Vultr-locked OpenTofu, self-managed k3s, channel templates, local-first
deployment scripts, GitOps, runtime secrets, storage, ingress, data plane,
application workloads, auth, policy, tenant isolation, and observability. The
local channel runs k3s through k3d. Remote channels describe k3s on Vultr Cloud
Compute VMs bootstrapped by cloud-init.

Local is a real deployment target, not a dry run. The completion proof creates
`humility-local`, installs Flux source and kustomize controllers, seeds an
in-cluster Git source from the local GitOps snapshot, and reaches it with
`kubectl` through `~/.kube/humility-local.yaml`. Remote Vultr work is
plan-only until post-INIT-117 deployment work supplies credentials and applies
a remote channel.

## Local Prerequisites

Required tools: OpenTofu `1.11.5`, kubectl `>= 1.31`, Docker `>= 24`,
Python `>= 3.10` with `jsonschema` and `PyYAML`, k3d `v5.8.3`, Flux
`v2.8.6`, Helm `v3.20.2`, SOPS `v3.12.2`, age/age-keygen `v1.3.1`,
Infisical CLI `v0.43.78`, and MinIO Client
`RELEASE.2025-08-13T08-35-41Z`. The `step`, `cmctl`, and `crossplane` CLIs are
useful for manual diagnosis, but INIT-105 and INIT-106 validation use
Kubernetes resources and do not require those host binaries.

Verify or install the pinned local cluster and GitOps toolchain:

```bash
bash infra/scripts/install-cluster-tools.sh --check
bash infra/scripts/install-cluster-tools.sh --install
```

`--install` writes k3d, flux, helm, sops, age, age-keygen, infisical, and mc to
`~/.local/bin`. Helm is local render tooling only; it is not installed into
the cluster. The script does not install OpenTofu, kubectl, Docker, Python,
`jsonschema`, or `PyYAML`.

## Layout

```text
infra/
  bootstrap/state-backend/          # Vultr Object Storage tfstate root
  channels/
    local.yaml                      # Local k3d channel
    dev.yaml                        # Remote Vultr VM plan channel
    fixtures/                       # Resolver and spawn fixtures
  schemas/                          # Source and resolved channel schemas
  scripts/                          # Tool install, channel, spawn, k3d ops
  modules/
    platform-cluster-k3d/           # Local k3d target
    platform-cluster-vms/           # Vultr VM plus cloud-init k3s target
    platform-network/               # Vultr VPC module
  templates/platform-channel/       # Shared root template and dispatch
  roots/channels/local/             # Committed local OpenTofu root
  roots/channels/dev/               # Committed remote plan OpenTofu root
  tests/validate_platform_bootstrap.sh
  tests/validate_observability_local.sh
```

Retired INIT-008 artifacts are intentionally absent: no
`infra/modules/platform-cluster/`, no `infra/environments/`, and no active
VKE-shaped channel fields.

## Channel Pattern

Channels are the environment model. A channel YAML declares provider, k3s
target, state backend, exposure class, inheritance parent, and whether
ephemeral children are allowed. Active declarations are
`infra/channels/local.yaml` and `infra/channels/dev.yaml`.

Resolve and validate channels:

```bash
python infra/scripts/resolve_platform_channel.py --channel local
python infra/scripts/resolve_platform_channel.py --channel dev
python infra/scripts/validate_platform_channels.py
```

Committed generated roots under `infra/roots/channels/{local,dev}/` are
drift-checked by the harness. `cluster.target` dispatches through
`infra/templates/platform-channel`: `k3d-local` calls
`infra/modules/platform-cluster-k3d`, and `vultr-vms` calls
`infra/modules/platform-cluster-vms`.

`local` resolves to `k3d-local`, k3s `v1.32.13+k3s1`, one server, one agent,
registry `humility-local`, and kubeconfig `~/.kube/humility-local.yaml`.

`dev` resolves to `vultr-vms`, k3s `v1.32.13+k3s1`, region `ewr`, one
`vc2-2c-4gb` server, zero agents, empty `vultr_ssh_key_ids`, and empty
`vultr_allowed_ssh_cidrs`.

## Local Channel Bring-Up

Verify local tooling:

```bash
bash infra/scripts/install-cluster-tools.sh --check
docker info
kubectl version --client
tofu version
```

Create, verify, repair, recreate, and tear down the local channel:

```bash
bash infra/scripts/bring-up-local-channel.sh local
KUBECONFIG=~/.kube/humility-local.yaml kubectl get nodes
KUBECONFIG=~/.kube/humility-local.yaml kubectl get pods -A
bash infra/scripts/bring-up-local-channel.sh --channel local --repair
bash infra/scripts/bring-up-local-channel.sh --channel local --force
bash infra/scripts/delete-local-channel.sh --channel local
```

The script resolves `local.yaml`, creates `humility-local` if needed, writes
`~/.kube/humility-local.yaml`, and verifies one server plus one agent. A second
run is a no-op when the live cluster matches the channel contract. The delete
script is idempotent when the cluster and kubeconfig are absent.

INIT-106 mounts `/var/run/docker.sock` into the local control-cluster nodes so
the Crossplane local AppCluster composition can create a nested k3d app cluster
from a Kubernetes Job. This is local-only proof machinery, not the security
baseline. `delete-local-channel.sh` deletes `humility-local-app` before deleting
`humility-local`.

Focused AppCluster proof after local bring-up:

```bash
bash infra/tests/validate_app_clusters_local.sh \
  --kubeconfig ~/.kube/humility-local.yaml
```

Expected proof points are Crossplane Deployments Available, provider packages
Healthy=True, `AppCluster/local-sample` Ready=True, and nested k3d cluster
`humility-local-app` nodes Ready.

## Runtime Secrets (Infisical)

INIT-103 adds the runtime secret-management layer for the local channel.
Infisical OSS, its in-cluster PostgreSQL and Redis dependencies, the Infisical
Kubernetes Operator, and the sample `InfisicalSecret` proof are reconciled by
Flux from `gitops/channels/local/infisical/`.

Runtime-secret toolchain prerequisites are Helm `v3.20.2` and Infisical CLI
`v0.43.78` in addition to the INIT-102 local GitOps tools. Helm is render-time
only: manifests are committed as raw YAML, and no Helm controller or
`HelmRelease` runs in the cluster.

Operator one-time bootstrap:

1. Generate or reuse the operator-local age key:

   ```bash
   bash infra/scripts/bootstrap-sops-age-key.sh --channel local
   ```

2. Replace the age recipient in `.sops.yaml` with the printed public key, then
   re-encrypt both bootstrap-only files for that recipient:

   ```bash
   sops updatekeys -y gitops/bootstrap/sops-sentinel.enc.yaml
   sops updatekeys -y gitops/bootstrap/infisical-server-bootstrap.enc.yaml
   ```

   This is the only SOPS step for INIT-103: it rotates bootstrap-file
   recipients to the operator's age key. Runtime secrets still do not enter
   SOPS.

3. Bring up the local channel:

   ```bash
   bash infra/scripts/bring-up-local-channel.sh local
   ```

   The post-Flux script renders and seeds the local GitOps source, delivers
   the Flux SOPS age key, waits for the Infisical server, runs
   `infra/scripts/bootstrap-infisical-identity.sh`, applies
   `Secret/infisical-operator-auth`, runs
   `infra/scripts/bootstrap-infisical-storage.sh`, waits for the Operator, and
   then waits for the sample runtime Secret.

Verify the runtime proof:

```bash
KUBECONFIG=~/.kube/humility-local.yaml \
  kubectl get infisicalsecret,secret -n infisical-sample
```

Expected resources include `InfisicalSecret/infisical-local-sample` and
`Secret/infisical-local-sample`. The target Secret must contain
`INFISICAL_SAMPLE_KEY=infisical-local-ready`.

Tear down with the same local delete path:

```bash
bash infra/scripts/delete-local-channel.sh --channel local
```

Troubleshooting an `InfisicalSecret` that is not reconciling starts with:

```bash
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n infisical-sample describe infisicalsecret infisical-local-sample
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n infisical-system logs deploy/infisical-opera-controller-manager
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n infisical-system get secret infisical-operator-auth
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n infisical-system logs deploy/infisical-infisical-standalone-infisical
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n flux-system describe kustomization humility-local
```

If the server is unavailable, also inspect `StatefulSet/postgresql`,
`StatefulSet/redis-master`, their PVCs, and
`Secret/infisical-server-bootstrap` in `infisical-system`.

Boundary: SOPS+age stays bootstrap-only. The only encrypted bootstrap files are
the Flux sentinel and Infisical server bootstrap Secret under
`gitops/bootstrap/`. Infisical owns runtime secrets, including downstream
application, object storage, database, Discord, and service credentials.
The local Infisical chart references `Secret/infisical-server-bootstrap` for
the server connection strings and the bundled Postgres/Redis passwords; rendered
manifests must not commit chart-default credential literals.

INIT-107 owns Infisical NetworkPolicy isolation through raw manifests in
`gitops/channels/local/security/`. The Bitnami chart defaults stay disabled in
`gitops/channels/local/infisical/server/render-values.yaml` because those
defaults look restrictive while allowing broad ingress or egress. The committed
baseline applies default-deny to `infisical-system`, then explicitly permits
only Infisical-to-Postgres, Infisical-to-Redis, operator-to-Infisical, API
server egress, and DNS egress.

## Cluster Security

INIT-107 adds the local cluster security baseline:

- PSS labels on managed namespaces: system namespaces enforce `baseline`,
  app/data namespaces enforce `restricted`.
- `app-cluster-system` is the only local privileged exception because the
  INIT-106 nested-k3d proof still uses `/var/run/docker.sock`.
- Default-deny NetworkPolicies plus explicit allow rules isolate Infisical,
  Postgres, Redis, MinIO, and restricted sample namespaces.
- provider-kubernetes no longer has cluster-admin; its injected identity is
  bound only to app-cluster-system Jobs and Events.
- Postgres, Redis, and MinIO have single-replica PDBs with `minAvailable: 1`.

Focused proof:

```bash
bash infra/tests/validate_cluster_security_local.sh \
  --kubeconfig ~/.kube/humility-local.yaml
```

## Object Storage

INIT-104 adds a local S3-compatible storage proof. Flux reconciles raw MinIO
manifests from `gitops/channels/local/object-storage/`: namespace,
`InfisicalSecret/minio-root`, single-node `Deployment/minio`,
`PersistentVolumeClaim/minio-data`, internal `Service/minio`, and
`Job/create-sample-bucket`.

Local credentials live in Infisical project `platform-storage`, environment
`local`, path `/object-storage/local/`. The bootstrap script seeds
`MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` only when absent and reuses
`Secret/infisical-operator-auth`; it does not create a storage-specific
Universal Auth Secret.

The generic S3 contract is:

```text
S3_ENDPOINT
S3_ACCESS_KEY_ID
S3_SECRET_ACCESS_KEY
S3_REGION
S3_BUCKET
```

Local values resolve to endpoint
`http://minio.minio-system.svc.cluster.local:9000`, region `us-east-1`, and
bucket `humility-local-sample`. Verify a live endpoint through the harness or
manually with:

```bash
KUBECONFIG=~/.kube/humility-local.yaml \
  bash infra/tests/validate_object_storage_local.sh
```

The standalone script below works against any S3-compatible endpoint when the
five `S3_*` variables are present:

```bash
bash infra/scripts/test-s3-roundtrip.sh --dry-run
bash infra/scripts/test-s3-roundtrip.sh
```

Troubleshooting starts with:

```bash
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n minio-system get infisicalsecret,secret,pvc,deploy,job,pod
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n minio-system describe infisicalsecret minio-root
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n minio-system logs deploy/minio
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n minio-system logs job/create-sample-bucket
```

Rollback for local development is the normal local-channel delete:
`bash infra/scripts/delete-local-channel.sh --channel local`. The next
bring-up reseeds Infisical storage credentials idempotently and recreates the
MinIO PVC and bucket.

## TLS And DNS

INIT-105 adds local certificate issuance and local service-name DNS. Flux
reconciles raw manifests from `gitops/channels/local/tls/` and
`gitops/channels/local/dns/`.

Local TLS components:

- cert-manager `v1.20.2`, rendered from the upstream chart with CRDs included.
- step-ca chart `1.30.1`, app `0.30.2`, deployed in `step-ca-system`.
- step-issuer chart `1.10.2`, app `0.10.2`, deployed in
  `step-issuer-system`.
- `StepClusterIssuer/humility-local-step-ca`, generated after step-ca writes
  its local root and provisioner credentials.
- `Certificate/cert-manager-test/humility-local-sample`, issuing
  `Secret/humility-local-sample-tls` for
  `minio.minio-system.humility.local`.

Local DNS uses the k3s CoreDNS ConfigMap in `kube-system`. The managed Corefile
keeps normal Kubernetes DNS behavior and rewrites `*.humility.local` to
`*.svc.cluster.local`, so internal services can be addressed by local channel
names before ingress exists.

Verify the focused local proof after the local channel is up:

```bash
KUBECONFIG=~/.kube/humility-local.yaml \
  bash infra/tests/validate_tls_dns_local.sh
```

Expected proof points:

```bash
KUBECONFIG=~/.kube/humility-local.yaml \
  kubectl get stepclusterissuer.certmanager.step.sm humility-local-step-ca
KUBECONFIG=~/.kube/humility-local.yaml \
  kubectl get certificate -n cert-manager-test humility-local-sample
```

Troubleshooting starts with:

```bash
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n cert-manager get deploy,pod
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n step-ca-system get job,sts,pod,cm,secret
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n step-issuer-system logs deploy/step-issuer
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n cert-manager-test describe certificate humility-local-sample
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n kube-system get configmap coredns -o yaml
```

Remote TLS/DNS is a contract only in INIT-105. Manifests live under
`gitops/contracts/remote/tls-dns/` and are not referenced by the local channel.
The Cloudflare API token must come from Infisical project `platform-dns`,
environment `dev`, path `/dns/dev/`, key `CLOUDFLARE_API_TOKEN`; it must not be
stored in SOPS. ExternalDNS and the Let's Encrypt staging ACME `ClusterIssuer`
are config-only until remote deployment work after INIT-117.

## GitOps Substrate

INIT-102 adds the canonical local GitOps reconciliation path. The local channel
installs pinned Flux `v2.8.6` source and kustomize controllers from
`gitops/flux/gotk-components.yaml`, serves a rendered repository snapshot from
an in-cluster Git daemon, and reconciles `GitRepository/humility-local` plus
`Kustomization/humility-local` in `flux-system`.

Operator one-time bootstrap:

1. Generate or reuse the operator-local age private key:

   ```bash
   bash infra/scripts/bootstrap-sops-age-key.sh --channel local
   ```

   The default key path is `~/.config/sops/age/local.txt`, with mode `0600`.

2. Replace the age recipient in `.sops.yaml` with the printed public key, then
   re-encrypt `gitops/bootstrap/sops-sentinel.enc.yaml` with that recipient:

   ```bash
   tmp_sentinel="$(mktemp)"
   cat > "${tmp_sentinel}" <<'YAML'
   apiVersion: v1
   kind: Secret
   metadata:
     name: sops-sentinel
     namespace: flux-system
     labels:
       channel: local
       sentinel: sops-local-ready
   type: Opaque
   stringData:
     ready: "true"
   YAML
   sops --encrypt \
     --filename-override gitops/bootstrap/sops-sentinel.enc.yaml \
     "${tmp_sentinel}" > gitops/bootstrap/sops-sentinel.enc.yaml
   rm -f "${tmp_sentinel}"
   ```

3. Bring up the local channel and Flux reconciliation:

   ```bash
   bash infra/scripts/bring-up-local-channel.sh local
   ```

Verify reconciliation:

```bash
KUBECONFIG=~/.kube/humility-local.yaml kubectl get gitrepository,kustomization -A
```

All listed Flux resources should report `Ready=True`.

### Reseeding the local gitserver after local manifest changes

Use this when an existing `humility-local` cluster is healthy enough to reach
with `~/.kube/humility-local.yaml`, but the in-cluster GitOps source is stale
relative to the checkout you want Flux to consume. The command renders the
current worktree into `.tmp/gitops-source/local`, force-pushes that snapshot to
the existing in-cluster `humility-local.git`, applies the generated Flux source
CRs, and waits for `GitRepository/humility-local` to report the new artifact
revision. It is not a full bootstrap: it does not run Infisical bootstraps,
Pomerium OIDC bootstrap, step-ca trust distribution, or resume the Flux
Kustomization.

Run the reseed from the checkout whose manifests should become the local
GitOps source:

```bash
bash infra/scripts/bring-up-local-channel.sh --channel local --reseed-gitserver-only
```

Verify the GitRepository observed the new synthetic revision:

```bash
KUBECONFIG=~/.kube/humility-local.yaml \
  kubectl get gitrepository -n flux-system humility-local
```

After the revision has advanced, resume Flux explicitly:

```bash
KUBECONFIG=~/.kube/humility-local.yaml \
  kubectl patch kustomization -n flux-system humility-local \
    --type=merge \
    -p '{"spec":{"suspend":false}}'
```

Watch reconcile:

```bash
KUBECONFIG=~/.kube/humility-local.yaml \
  flux reconcile kustomization humility-local \
    --namespace flux-system \
    --with-source

KUBECONFIG=~/.kube/humility-local.yaml \
  kubectl -n flux-system wait kustomization/humility-local \
    --for=condition=Ready \
    --timeout=300s
```

Tear down the local channel:

```bash
bash infra/scripts/delete-local-channel.sh --channel local
```

Troubleshooting Flux reconciliation starts with:

```bash
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n flux-system logs deploy/source-controller
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n flux-system logs deploy/kustomize-controller
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n flux-system describe gitrepository humility-local
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n flux-system describe kustomization humility-local
KUBECONFIG=~/.kube/humility-local.yaml kubectl -n git-system logs deploy/git-daemon
```

SOPS+age is bootstrap-only. The encrypted sentinel proves Flux can decrypt
bootstrap-tier manifests. Runtime application secrets, Discord tokens,
database passwords, and Infisical runtime data belong to Infisical in INIT-103.

## Remote Channel Plan-Only

The `dev` channel is a Vultr VM k3s plan surface. INIT-101 validates the shape
without spending Vultr resources:

```bash
cd infra/roots/channels/dev
tofu init -backend=false
tofu validate
```

Remote apply is post-INIT-117 deployment work. That work must define Vultr
credentials, SSH key IDs, backend initialization, bootstrap token handling,
kubeconfig retrieval, rollback, and `tofu apply` procedure. Do not run
`tofu apply` against `infra/roots/channels/dev` as part of INIT-101.

## Channel Registry And Spawn

To add a durable channel: add `infra/channels/<id>.yaml`, run
`validate_platform_channels.py`, resolve the channel, generate
`backend.tfbackend` and `channel.auto.tfvars.json`, then commit the source and
generated root artifacts together.

Spawn ephemeral children under `.tmp/` only:

```bash
python infra/scripts/spawn_platform_channel.py \
  --parent dev \
  --suffix pr-123 \
  --out .tmp/dev-pr-123
```

The spawn script refuses outputs outside `.tmp/` and parents with
`allow_ephemeral_children: false`. It does not create active files under
`infra/`.

## Local Verification

Canonical platform bootstrap verification without creating a cluster:

```bash
bash infra/tests/validate_platform_bootstrap.sh
```

Default mode validates files, schemas, resolver behavior, generator drift,
GitOps rendering, Flux lockfile shape, SOPS bootstrap boundary, OpenTofu
validation, cloud-init strictness, VKE retirement, and no-cluster script
idempotency.

Canonical real local cluster proof:

```bash
bash infra/tests/validate_platform_bootstrap.sh --cluster
```

Cluster mode requires Docker, k3d, kubectl, flux, helm, sops, age, age-keygen,
infisical, and mc. It verifies `kubectl get nodes` against
`~/.kube/humility-local.yaml`, confirms all nodes are `Ready`, waits for Flux
`GitRepository` and `Kustomization` readiness, waits for Infisical server,
PostgreSQL, Redis, Operator, Universal Auth, `InfisicalSecret`, and target
Secret readiness, verifies MinIO readiness, bucket creation, real S3
PUT/GET/compare/DELETE, MinIO Pod restart durability, verifies cert-manager,
step-ca, step-issuer, sample Certificate issuance, and CoreDNS
`humility.local` resolution, verifies the snapshot marker reached the cluster,
checks Postgres and git-daemon Pod restart recovery, reruns bring-up, repeats
the object-storage and TLS/DNS proofs, deletes the cluster, and checks delete
idempotency.

## Backup / DR

INIT-112 adds the platform backup contract, local CNPG scheduled backups to
MinIO bucket `humility-local-backups`, a deterministic restore drill, and a k3d
Docker-volume snapshot script for the local control cluster.

Static Backup / DR validation:

```bash
bash infra/tests/validate_backup_dr_local.sh --static-only
```

Runtime Backup / DR proof after local Flux reconciliation:

```bash
bash infra/tests/validate_backup_dr_local.sh \
  --channel local \
  --kubeconfig ~/.kube/humility-local.yaml
```

The runtime proof waits for `Job/create-backup-bucket`, verifies
`ScheduledBackup/sample-app-postgres-daily`, inserts a known row, creates a
manual CNPG `Backup`, verifies backup objects in MinIO, restores to a fresh
CNPG cluster, and checks both `sample_app.widgets` and the inserted row.

Create a local k3d control-cluster volume snapshot:

```bash
bash infra/scripts/snapshot-k3d-volumes.sh \
  --cluster humility-local
```

The `dev` channel records the Vultr Object Storage backup contract only. Bucket
creation and remote restore execution remain deployment work.

## Container Delivery

INIT-108 adds the channel image registry contract. The local channel pushes to
`localhost:5000` and Pods pull the same repository path through
`k3d-humility-local:5000`. Image names follow:

```text
<registry>/<channel>/<app>:<tag>
```

Local smoke build and push:

```bash
bash infra/scripts/build-channel-image.sh \
  --channel local \
  --app registry-smoke \
  --tag init-108 \
  --context containers/samples/registry-smoke \
  --file containers/samples/registry-smoke/Containerfile
```

Real local registry proof:

```bash
bash infra/tests/validate_container_delivery_local.sh \
  --channel local \
  --kubeconfig ~/.kube/humility-local.yaml
```

The local bring-up script creates Distribution proxy caches for Docker Hub,
Quay, and GHCR, then passes a K3s `registries.yaml` mirror config into k3d.
Remote `dev` records the Vultr Container Registry contract only:
`ewr.vultrcr.com/humility`, with `Secret/vultr-cr-credentials` in
`app-runtime` sourced from Infisical path `/registry/dev`.

## Observability

INIT-117 adds the local observability stack under
`gitops/channels/local/observability`:

The remote observability contract is intentionally config-only until
post-INIT-117 remote deployment work extends this local subtree for remote
object storage, ingress, retention, and alert routing.

- Prometheus raw manifests with local scrape config and basic alert rules.
- Grafana raw manifests with Prometheus/Loki datasources and dashboard
  ConfigMaps.
- Alertmanager raw manifests for local alert ingestion.
- OpenTelemetry Collector as a DaemonSet for OTLP trace and log intake.
- Loki raw manifests backed by the INIT-104 MinIO object store, using
  Infisical-managed credentials.
- ServiceMonitor resources for Flux, Crossplane, cert-manager, Infisical,
  MinIO, CNPG, Kong, Pomerium, Authentik, OPAL, the API workload, and
  Buildkite agent.
- Tenant-aware dashboards using `platform.humility.gg/tenant`.

Static proof:

```bash
bash infra/tests/validate_observability_local.sh --static-only
```

Runtime proof after local channel reconciliation:

```bash
bash infra/tests/validate_observability_local.sh \
  --kubeconfig ~/.kube/humility-local.yaml
```

The runtime proof checks observability Pods Ready, prints Prometheus targets,
confirms Grafana dashboard provisioning, sends a sample Alertmanager alert, and
pushes/queries a sample Loki log line.

## Anti-Scope

This directory does not install or operate:

- Vultr Object Storage bucket provisioning: later remote deployment work.
- Real Cloudflare DNS records and production ACME issuance: post-INIT-117
  deployment work.
- Remote k3s apply, remote HA execution, remote kubeconfig retrieval, or Vultr
  load balancer registration.
- Production SLI/SLO definitions, incident response automation, and
  third-party alert integrations.

Remote HA is scheduled for INIT-118. Remote apply is post-INIT-117 deployment
work.

## Cross-References

Controlling decision: `../planning/DECISIONS.md` D8, "Environment-agnostic Phase 5 reset:
local-as-first-deployment and self-managed k3s everywhere."

Workflow library references under `~/ai/` apply here, especially the
no-backwards-compatibility and unfinished-work conventions. D8 also points
future INIT proposals at the environment-agnostic stack reference: local is a
deployment target, channels carry provider configuration, and k3s is used
locally and remotely.

For contributors starting in `docs/`, see `../planning/docs/deployment-substrate.md` for
the short context handoff back to this README.
