# INIT-103 Phase 1 Research: Infisical Runtime Secret Store

## Scope

- Initiative: INIT-103.
- Phase: 1, problem/component research.
- Goal: document evidence for installing and operating Infisical as the platform runtime secret store.
- Rule: evidence only; proposal choices remain for the proposal phase.
- Boundary: INIT-102 owns Flux, channel GitOps, and bootstrap-only SOPS+age.
- Boundary: INIT-103 owns Infisical server, Infisical Operator, InfisicalSecret CRDs, RBAC, and runtime secret sync.
- Non-negotiable: Infisical is the runtime secret manager; alternatives are out of scope.
- Non-negotiable: local is a real first deployment target.
- Non-negotiable: remote remains Vultr-locked.
- Output path: `.pipeline/research.md`.

## Evidence Index

- E1: `DECISIONS.md:176-260` records D8: local-as-first-deployment, k3s everywhere, Flux, SOPS bootstrap-only, and Infisical runtime secrets.
- E2: `product-strategy/tickets/PHASE_5_INDEX.md:1-11` states Phase 5 uses the same local/remote stack and Infisical is runtime secret store.
- E3: `product-strategy/tickets/PHASE_5_INDEX.md:26-45` places INIT-103 after INIT-102 and before MinIO, DNS/TLS, data plane, and workloads.
- E4: `product-strategy/tickets/PHASE_5_INDEX.md:96-130` states local is a deployment target and runtime secrets go through Infisical.
- E5: `~/.claude3/projects/-home-nes-projects-server-manager/memory/environment-agnostic-stack.md` states local and remote run the same components, with Infisical in both.
- E6: `~/.claude3/projects/-home-nes-projects-server-manager/memory/channel-template-pattern.md` states channels replace hard dev/staging/prod roots.
- E7: `infra/channels/local.yaml:1-32` defines the local channel as k3s on k3d with a concrete GitOps block.
- E8: `infra/channels/dev.yaml:1-28` defines the dev channel as k3s on Vultr VMs and deliberately omits GitOps in INIT-102.
- E9: `infra/schemas/platform-channel.schema.json:1-84` defines the channel schema and requires `gitops` for `k3d-local`.
- E10: `infra/schemas/platform-channel.schema.json:270-335` defines the current `gitops` object shape.
- E11: `gitops/README.md:5-16` documents the INIT-102 GitOps layout and says runtime app secrets move through Infisical in INIT-103.
- E12: `infra/README.md:188-190` says SOPS+age is bootstrap-only and runtime app secrets, Discord tokens, DB passwords, and Infisical runtime data belong to Infisical in INIT-103.
- E13: `infra/README.md:230-252` documents INIT-102 default and cluster verification and its required tools.
- E14: `infra/README.md:254-264` lists runtime secret management and Infisical installation as INIT-103 anti-scope for INIT-102.
- E15: `infra/scripts/lint-sops-boundary.py:14-22` defines the allowed encrypted file and runtime-secret-shaped reject patterns.
- E16: `infra/scripts/lint-sops-boundary.py:63-98` enforces exactly one SOPS encrypted file under `gitops/bootstrap`.
- E17: `infra/tests/validate_platform_bootstrap.sh:124-174` validates `.sops.yaml`, the encrypted sentinel, and SOPS boundary lint.
- E18: `infra/tests/validate_platform_bootstrap.sh:176-239` verifies the local channel GitOps block and the dev omission.
- E19: `/home/nes/projects/server-manager/worktrees/init-102-gitops-substrate/.pipeline/implementation.md:61-83` hands INIT-103 the local channel overlay and bootstrap-only age key boundary.
- E20: `/home/nes/projects/server-manager/worktrees/init-102-gitops-substrate/.pipeline/implementation.md:84-94` lists INIT-103 open questions.
- E21: `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/.pipeline/proposal.md:39-73` is archived context with kind/local-verification framing, now superseded.
- E22: Infisical Kubernetes Operator overview: https://infisical.com/docs/integrations/platforms/kubernetes/overview
- E23: InfisicalSecret CRD docs: https://infisical.com/docs/integrations/platforms/kubernetes/infisical-secret-crd
- E24: Infisical Kubernetes Helm self-hosting docs: https://infisical.com/docs/self-hosting/deployment-options/kubernetes-helm
- E25: Infisical Docker self-hosting docs: https://infisical.com/docs/self-hosting/deployment-options/standalone-infisical
- E26: Infisical Docker Compose self-hosting docs: https://infisical.com/docs/self-hosting/deployment-options/docker-compose
- E27: Infisical environment variables docs: https://infisical.com/docs/self-hosting/configuration/envars
- E28: Infisical Universal Auth docs: https://infisical.com/docs/documentation/platform/identities/universal-auth
- E29: Infisical Kubernetes Auth docs: https://infisical.com/docs/documentation/platform/identities/kubernetes-auth
- E30: Infisical project model docs: https://infisical.com/docs/documentation/platform/secrets-mgmt/project
- E31: Infisical folder model docs: https://infisical.com/docs/documentation/platform/folder
- E32: Infisical Kubernetes Operator repository: https://github.com/Infisical/kubernetes-operator
- E33: Infisical main repository Docker Compose: https://github.com/Infisical/infisical/blob/main/docker-compose.prod.yml
- E34: Infisical CLI releases: https://github.com/Infisical/cli/releases
- E35: Local clone evidence: `.tmp/infisical-kubernetes-operator-v0.10.32/config/crd/bases/*.yaml`, tag `infisical-k8-operator/v0.10.32`.
- E36: Local clone evidence: `.tmp/infisical-kubernetes-operator-v0.10.32/helm-charts/secrets-operator/values.yaml`.
- E37: Toolchain check run in this worktree on 2026-04-26.

## 1. Current Repo State

### 1.1 Phase 5 control facts

- Phase 5 is now governed by local-as-first-deployment, not local simulation. [E1]
- Phase 5 uses self-managed k3s everywhere: k3d locally and k3s on Vultr Cloud Compute VMs remotely. [E1]
- Flux remains the GitOps reconciler. [E1]
- SOPS+age remains bootstrap-only. [E1]
- Infisical is the runtime secret store. [E1]
- Channel templates remain the environment model. [E1]
- Per-channel config is expected to carry Infisical endpoint information. [E1]
- Every Phase 5 initiative must deploy a real component into the local channel as its done state. [E1]
- The Phase 5 index repeats that local and remote run the same stack with per-channel configuration. [E2]
- The Phase 5 index repeats that SOPS+age is bootstrap-only and Infisical is runtime. [E2]
- INIT-103 is named "Infisical runtime secret store." [E3]
- INIT-103 scope includes Infisical, Infisical Operator, InfisicalSecret CRDs, RBAC, and runtime secret ownership. [E3]
- INIT-103 depends on INIT-102. [E3]
- INIT-104 depends on INIT-103 because MinIO credentials flow through Infisical. [E3]
- INIT-111 depends on INIT-103 because database credentials flow through Infisical. [E3]
- INIT-113 depends on INIT-103 because workloads require runtime secrets. [E3]
- Phase 5 completion requires Infisical to own runtime secrets and sync them through the Operator. [E4]

### 1.2 INIT-102 substrate available to INIT-103

- The current local channel is `id: local`. [E7]
- The current local channel uses `cluster.distribution: k3s`. [E7]
- The current local channel target is `k3d-local`. [E7]
- The current local k3d shape is one server and one agent. [E7]
- The current local channel includes a concrete `gitops` block. [E7]
- The local GitOps source URL points at an in-cluster `git-local.git-system.svc.cluster.local` service. [E7]
- The local GitOps path is `./gitops/channels/local`. [E7]
- The local Flux Kustomization name is `humility-local`. [E7]
- The local SOPS age secret name is `sops-age`. [E7]
- The local decryption secret namespace is `flux-system`. [E7]
- The current remote plan channel is `id: dev`. [E8]
- The current remote plan channel target is `vultr-vms`. [E8]
- The current remote plan channel uses Vultr region `ewr`. [E8]
- The current remote plan channel defines one server VM on `vc2-2c-4gb`. [E8]
- The current remote plan channel deliberately omits `gitops` in INIT-102. [E8]
- The channel schema requires `cluster` and `state` when `parent` is null. [E9]
- The channel schema requires `gitops` when the cluster target is `k3d-local`. [E9]
- The existing `gitops` schema is strict with `additionalProperties: false`. [E10]
- The existing `gitops` schema requires source kind, URL, ref, path, Kustomization names, SOPS secret names, intervals, prune, and wait. [E10]
- INIT-102 therefore gives INIT-103 an existing strict schema pattern to extend. [E9, E10]
- `gitops/README.md` lists `gitops/flux`, `gitops/sources/local`, `gitops/channels/local`, and `gitops/bootstrap`. [E11]
- `gitops/README.md` says runtime application secrets do not live in `gitops/bootstrap`. [E11]
- `infra/README.md` says the encrypted sentinel proves Flux can decrypt bootstrap-tier manifests. [E12]
- `infra/README.md` says runtime application secrets, Discord tokens, DB passwords, and Infisical runtime data belong to Infisical in INIT-103. [E12]
- INIT-102 cluster verification requires Docker, k3d, kubectl, flux, sops, age, and age-keygen. [E13]
- INIT-102 cluster verification waits for Flux source and Kustomization readiness. [E13]
- INIT-102 cluster verification checks a snapshot marker and SOPS Secret reached the cluster. [E13]
- INIT-102 anti-scope explicitly excludes runtime secret management and Infisical installation. [E14]

### 1.3 SOPS bootstrap boundary currently enforced

- The SOPS boundary linter allows exactly `gitops/bootstrap/sops-sentinel.enc.yaml`. [E15, E16]
- The linter treats path/key patterns beginning with `infisical` as runtime-secret-shaped. [E15]
- The linter treats `discord.*token` as runtime-secret-shaped. [E15]
- The linter treats `password` as runtime-secret-shaped. [E15]
- The linter treats `secret_access_key` and `api_key` as runtime-secret-shaped. [E15]
- The linter fails if the encrypted file set is anything other than the one sentinel file. [E16]
- The harness validates exactly one SOPS creation rule. [E17]
- The harness validates that the SOPS creation rule only targets `gitops/bootstrap/*.enc.yaml`. [E17]
- The harness validates that encrypted fields match `data|stringData`. [E17]
- The harness runs the SOPS boundary linter. [E17]
- The existing guard means INIT-103 cannot add runtime secrets as additional SOPS files without changing the boundary. [E15, E16, E17]
- The existing guard also means an Infisical bootstrap credential needs explicit boundary treatment if it enters through SOPS. [E15, E16]

### 1.4 Current lack of Infisical resources

- `rg` found no committed Infisical Operator manifests under the current `gitops/` tree. [E37]
- `rg` found no committed `InfisicalSecret` CRs under the current `gitops/` tree. [E37]
- `rg` found only planning/documentation references to Infisical in current repo files. [E37]
- The current GitOps channel overlay contains the namespace, snapshot marker, and SOPS sentinel only. [E11]
- The current schema contains no top-level `infisical` block. [E9, E10]
- The current `local.yaml` contains no Infisical server URL, project ID, environment slug, or service-token Secret reference. [E7]
- The current `dev.yaml` contains no Infisical server URL, project ID, environment slug, or service-token Secret reference. [E8]
- INIT-102 handoff says INIT-103 should install the Infisical Operator through Flux under `gitops/channels/local/`. [E19]
- INIT-102 handoff says runtime `InfisicalSecret` resources are INIT-103's contract. [E19]
- INIT-102 handoff says runtime application secrets must not be encoded in SOPS files. [E19]
- INIT-102 open questions include Infisical server URL representation. [E20]
- INIT-102 open questions include whether project ID is one-per-channel, inherited, or tenant/application split. [E20]
- INIT-102 open questions include where the Infisical service token enters bootstrap. [E20]
- INIT-102 open questions include Operator namespace and target namespace authorization. [E20]
- INIT-102 open questions include readiness assertions after `InfisicalSecret` reconciliation exists. [E20]

### 1.5 Archived anti-pattern context

- The archived INIT-009 proposal used local verification framing that is superseded by D8. [E21, E1]
- The archived INIT-009 proposal used `kind`, while D8 supersedes local kind with k3d because k3d runs k3s. [E21, E1]
- The archived INIT-009 proposal treated SOPS+age as a broader GitOps secret mechanism, while D8 narrows SOPS+age to bootstrap-only. [E21, E1]
- The archived INIT-009 material is useful only as context for what INIT-103 should not reproduce. [E21, E1]

## 2. Infisical Open Source Self-Hosted Architecture

### 2.1 Component inventory

- Infisical self-hosting docs describe a Docker deployment using the `infisical/infisical` image plus external Postgres and Redis dependencies. [E25]
- The standalone Docker docs say the image contains application code only and requires Postgres and Redis connections. [E25]
- The Docker Compose example defines a `backend` service using `infisical/infisical:latest` and explicitly comments to pin a specific tag. [E33]
- The Docker Compose example defines a `db` service using `postgres:14-alpine`. [E33]
- The Docker Compose example defines a `redis` service using `redis`. [E33]
- The Docker Compose example puts Postgres data in a `pg_data` volume. [E33]
- The Docker Compose example puts Redis data in a `redis_data` volume. [E33]
- The Kubernetes Helm docs show the application image repository as `infisical/infisical`. [E24]
- The Kubernetes Helm docs show example image tag `v0.151.0`. [E24]
- The Kubernetes Helm docs state not to use `latest` in production and to pin a specific version. [E24]
- The Kubernetes Helm docs show a normal running deployment with Infisical pods plus `postgresql-0` and `redis-master-0`. [E24]
- The Kubernetes Helm docs state the application layer is stateless and can scale horizontally. [E24]
- The Kubernetes Helm values reference shows default `infisical.replicaCount: 2`. [E24]
- The Kubernetes Helm values reference shows `infisical.resources.requests.cpu: 350m`. [E24]
- The Kubernetes Helm values reference shows `infisical.resources.limits.memory: 1000Mi`. [E24]
- The Kubernetes Helm values reference shows in-cluster PostgreSQL enabled by default. [E24]
- The Kubernetes Helm values reference shows in-cluster Redis enabled by default. [E24]
- The Kubernetes Helm values reference shows PostgreSQL image repository `bitnamilegacy/postgresql`. [E24]
- The Kubernetes Helm values reference shows Redis image repository `bitnamilegacy/redis`. [E24]
- The Kubernetes Helm docs state proof-of-concept deployments can use chart-provisioned in-cluster PostgreSQL and Redis. [E24]
- The Kubernetes Helm docs state in-cluster PostgreSQL and Redis are not high availability. [E24]
- The Kubernetes Helm docs recommend external managed PostgreSQL and Redis for production HA. [E24]
- The Kubernetes Helm docs describe default PVCs for PostgreSQL and Redis when in-cluster databases are used. [E24]
- The Kubernetes Helm docs list default PVC size 8Gi for PostgreSQL data. [E24]
- The Kubernetes Helm docs list default PVC size 8Gi for Redis data. [E24]
- The Kubernetes Helm docs say the PostgreSQL PVC contains encrypted secrets and should not be deleted unless data loss is intended. [E24]

### 2.2 Required configuration and first-run data

- Infisical accepts self-hosted configuration through environment variables. [E27]
- Minimal self-hosting requires `ENCRYPTION_KEY`, `AUTH_SECRET`, `DB_CONNECTION_URI`, and `REDIS_URL`. [E27]
- `ENCRYPTION_KEY` is required. [E27]
- `ENCRYPTION_KEY` must be a random 16-byte hex string. [E27]
- `AUTH_SECRET` is required. [E27]
- `AUTH_SECRET` must be a random 32-byte base64 string. [E27]
- `SITE_URL` is required. [E27]
- `SITE_URL` must be an absolute URL including protocol. [E27]
- `PORT` defaults to `8080`. [E27]
- `HOST` defaults to `localhost`. [E27]
- `HOST=0.0.0.0` is needed for external accessibility in self-hosted deployments. [E27]
- The sample `.env.example` uses `DB_CONNECTION_URI=postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}`. [E33]
- The sample `.env.example` uses `REDIS_URL=redis://redis:6379`. [E33]
- The sample `.env.example` includes `KUBERNETES_AUTO_FETCH_SERVICE_ACCOUNT_TOKEN=false`. [E33]
- The Kubernetes Helm docs create `Secret/infisical-secrets` with `AUTH_SECRET`, `ENCRYPTION_KEY`, and `SITE_URL` for proof-of-concept installs. [E24]
- The Kubernetes Helm docs add `DB_CONNECTION_URI` and `REDIS_URL` when external database and Redis are used. [E24]
- The Kubernetes Helm docs state the first user to sign up becomes the instance administrator. [E24]
- The Kubernetes Helm values reference includes `autoBootstrap.enabled: false` by default. [E24]
- The Kubernetes Helm values reference includes an auto-bootstrap secret destination named `infisical-bootstrap-secret`. [E24]
- The Kubernetes Helm values reference includes a bootstrap credential secret named `infisical-bootstrap-credentials`. [E24]
- The auto-bootstrap fields are evidence of a chart-supported bootstrap path, but the research did not validate its behavior end-to-end. [E24]

### 2.3 Resource footprint evidence

- Infisical application container chart defaults request 350m CPU. [E24]
- Infisical application container chart defaults limit 1000Mi memory. [E24]
- Infisical Operator chart defaults request 10m CPU. [E36]
- Infisical Operator chart defaults request 64Mi memory. [E36]
- Infisical Operator chart defaults limit 500m CPU. [E36]
- Infisical Operator chart defaults limit 128Mi memory. [E36]
- PostgreSQL default PVC size is 8Gi in the Helm docs. [E24]
- Redis default PVC size is 8Gi in the Helm docs. [E24]
- The local channel currently has one k3d server and one k3d agent. [E7]
- The remote dev VM plan currently has one `vc2-2c-4gb` server and no agents. [E8]
- The docs identify insufficient cluster resources and unbound PVCs as common pending-Pod causes. [E24]
- The docs recommend checking resource limits and scaling horizontally for performance issues. [E24]
- The docs do not document SQLite as an Infisical self-hosted storage option. [E24, E25, E27]
- The docs consistently require Postgres and Redis for self-hosted Infisical. [E24, E25, E27]
- Evidence therefore indicates k3d local needs PVC-backed Postgres and Redis, not SQLite. [E24, E25, E27]

### 2.4 Supported install methods and GitOps implications

- Infisical documents Docker Compose for a single Docker host. [E26]
- Infisical documents standalone Docker with externally supplied Postgres and Redis. [E25]
- Infisical documents Kubernetes installation through a Helm chart. [E24]
- Infisical Kubernetes Helm install command uses `helm upgrade --install infisical infisical-helm-charts/infisical-standalone`. [E24]
- Infisical Operator docs install the Operator through Helm. [E22]
- Infisical Operator repository also contains Kustomize-style `config/default`, `config/crd`, `config/rbac`, and `config/manager` directories. [E32, E35]
- Infisical Operator repository also contains a `kubectl-install/install-secrets-operator.yaml` file. [E32, E35]
- INIT-102 installed only Flux source-controller and kustomize-controller, not helm-controller. [E19, E11]
- INIT-102 local channel reconciles through Flux Kustomization from raw Git manifests. [E7, E11, E19]
- INIT-103's raw-manifest need follows from INIT-102's reconciler shape, not from Infisical docs. [E7, E10, E19, E22, E24]
- Helm charts remain useful as upstream source material for rendered manifests and defaults. [E22, E24, E36]
- A proposal that uses raw committed manifests needs a version pin for both Infisical server image and Operator manifests. [E24, E32, E36]

## 3. Infisical Kubernetes Operator

### 3.1 Operator role and reconciliation model

- Infisical describes the Operator as Kubernetes controllers for managing secrets between Infisical and Kubernetes. [E22]
- The Operator supports syncing secrets from Infisical into Kubernetes through `InfisicalSecret`. [E22]
- The Operator supports pushing Kubernetes secrets to Infisical through `InfisicalPushSecret`. [E22]
- The Operator supports dynamic secrets and leases through `InfisicalDynamicSecret`. [E22]
- Infisical docs say configured CRDs are continuously monitored and updated to keep Kubernetes secrets current. [E22]
- Infisical docs say the Operator can automatically reload dependent workload resources when relevant secrets are updated. [E22, E23]
- InfisicalSecret docs say managed Kubernetes Secret targets are defined through `managedKubeSecretReferences`. [E23]
- InfisicalSecret docs say the Operator creates managed Kubernetes Secrets in the specified name and namespace. [E23]
- InfisicalSecret docs say `managedSecretReference` is deprecated and replaced by `managedKubeSecretReferences`. [E23]
- InfisicalSecret docs say `managedKubeSecretReferences` accepts an array, allowing multiple managed Secret outputs from one CR. [E23]
- InfisicalSecret docs say creation policy can be `Orphan` or `Owner`. [E23]
- InfisicalSecret docs say `Owner` requires the InfisicalSecret CR to be in the same namespace as the managed Secret. [E23]
- InfisicalSecret docs say templating can transform fetched secrets before writing Kubernetes Secrets. [E23]
- InfisicalSecret docs say managed ConfigMaps are for non-sensitive data and managed Secrets should be used for sensitive data. [E23]

### 3.2 CRD set and API details

- The current operator docs list `InfisicalSecret`, `InfisicalPushSecret`, and `InfisicalDynamicSecret` as supported CRDs. [E22]
- The v0.10.32 operator repository CRD directory also contains `ClusterGenerator`, `Password`, and `UUID` CRDs. [E35]
- `InfisicalSecret` group is `secrets.infisical.com`. [E35]
- `InfisicalSecret` version is `v1alpha1`. [E35]
- `InfisicalSecret` kind is `InfisicalSecret`. [E35]
- `InfisicalSecret` scope is Namespaced. [E35]
- `InfisicalPushSecret` group is `secrets.infisical.com`. [E35]
- `InfisicalPushSecret` version is `v1alpha1`. [E35]
- `InfisicalPushSecret` kind is `InfisicalPushSecret`. [E35]
- `InfisicalPushSecret` scope is Namespaced. [E35]
- `InfisicalDynamicSecret` group is `secrets.infisical.com`. [E35]
- `InfisicalDynamicSecret` version is `v1alpha1`. [E35]
- `InfisicalDynamicSecret` kind is `InfisicalDynamicSecret`. [E35]
- `InfisicalDynamicSecret` scope is Namespaced. [E35]
- `ClusterGenerator` group is `secrets.infisical.com`. [E35]
- `ClusterGenerator` version is `v1alpha1`. [E35]
- `ClusterGenerator` kind is `ClusterGenerator`. [E35]
- `ClusterGenerator` scope is Cluster. [E35]
- `Password` group is `secrets.infisical.com`. [E35]
- `Password` version is `v1alpha1`. [E35]
- `Password` kind is `Password`. [E35]
- `Password` scope is Namespaced. [E35]
- `UUID` group is `secrets.infisical.com`. [E35]
- `UUID` version is `v1alpha1`. [E35]
- `UUID` kind is `UUID`. [E35]
- `UUID` scope is Namespaced. [E35]
- The operator docs call the CRD list expandable over time. [E22]
- The proposal phase needs to decide whether INIT-103 commits all upstream CRDs or only the CRDs needed for pull-based runtime sync. [E22, E35]

### 3.3 InfisicalSecret shape

- InfisicalSecret sample uses `apiVersion: secrets.infisical.com/v1alpha1`. [E23, E35]
- InfisicalSecret sample uses `kind: InfisicalSecret`. [E23, E35]
- InfisicalSecret sample includes `spec.hostAPI`. [E23, E35]
- InfisicalSecret sample includes `spec.syncConfig.resyncInterval`. [E23, E35]
- InfisicalSecret sample includes `spec.syncConfig.instantUpdates`. [E23, E35]
- InfisicalSecret supports a `tls.caRef` for a custom CA Secret. [E23, E35]
- InfisicalSecret supports Universal Auth through `authentication.universalAuth`. [E23, E35]
- Universal Auth scope can include `projectSlug`. [E23, E35]
- Universal Auth scope can include `projectId`. [E23, E35]
- Universal Auth scope includes `envSlug`. [E23, E35]
- Universal Auth scope includes `secretsPath`. [E23, E35]
- Universal Auth scope can include `recursive`. [E23, E35]
- Universal Auth credentials use a Kubernetes Secret reference with name and namespace. [E23, E35]
- InfisicalSecret supports Native Kubernetes Auth through `authentication.kubernetesAuth`. [E23, E35]
- Kubernetes Auth uses `serviceAccountRef`, `identityId`, and `secretsScope`. [E23, E35]
- InfisicalSecret supports service-token authentication through `authentication.serviceToken`. [E23, E35]
- Service-token authentication uses `serviceTokenSecretReference`. [E23, E35]
- Service-token authentication scope uses `envSlug` and `secretsPath`. [E23, E35]
- Service-token sample Secret stores the token under key `infisicalToken`. [E35]
- Universal Auth sample Secret stores `clientId` and `clientSecret`. [E35]
- Current samples show only one authentication method should be defined in one InfisicalSecret. [E35]
- The CRD docs state either `projectSlug` or `projectId` can be used in `secretsScope`. [E23]
- The CRD docs state only one of `projectSlug` or `projectId` should be used. [E23]

### 3.4 RBAC and namespace scope

- Operator docs describe a cluster-wide install where one operator manages secrets across namespaces. [E22]
- Operator docs say the cluster-wide install works out of the box with no additional RBAC configuration. [E22]
- Operator docs describe namespace-scoped installs for enhanced security and multi-tenant clusters. [E22]
- Operator docs say only the first namespace-scoped installation should install CRDs because CRDs are cluster-wide. [E22]
- Operator docs support `scopedNamespaces`. [E22, E36]
- Operator docs support `scopedRBAC`. [E22, E36]
- Operator docs support `installCRDs: false` for additional namespace-scoped installs. [E22, E36]
- Operator chart values default `scopedNamespaces: []`, meaning watch all namespaces. [E36]
- Operator chart values default `scopedRBAC: false`. [E36]
- Operator chart values default `installCRDs: true`. [E36]
- Operator chart values allow using a pre-existing service account. [E22, E36]
- Operator RBAC grants create/delete/get/list/update/watch on core `secrets`. [E35]
- Operator RBAC grants create/delete/get/list/update/watch on core `configmaps`. [E35]
- Operator RBAC grants get/list on pods. [E35]
- Operator RBAC grants get/list/watch on serviceaccounts. [E35]
- Operator RBAC grants create on serviceaccounts/token. [E35]
- Operator RBAC grants get/list/update/watch on deployments, daemonsets, and statefulsets. [E35]
- Operator RBAC grants create on tokenreviews. [E35]
- Operator RBAC grants create/delete/get/list/patch/update/watch on Infisical CRs. [E35]
- Operator RBAC grants update on Infisical CR finalizers. [E35]
- Operator RBAC grants get/patch/update on Infisical CR statuses. [E35]
- These RBAC permissions are broader than a pure read-from-Infisical/write-one-Secret path. [E35]
- Namespace scoping is therefore a meaningful proposal-phase security control. [E22, E35, E36]

### 3.5 Operator version and manifest pinning evidence

- GitHub reported latest operator release tag `infisical-k8-operator/v0.10.32` on 2026-04-26. [E32, E37]
- The cloned v0.10.32 chart reports chart version `v0.10.32`. [E36]
- The cloned v0.10.32 chart reports appVersion `v0.10.32`. [E36]
- The cloned v0.10.32 chart values still show manager image tag `v0.10.31`. [E36]
- The chart values tag/appVersion mismatch is an implementation risk to verify before pinning. [E36]
- The operator chart uses repository `infisical/kubernetes-operator`. [E36]
- The operator chart uses one replica by default. [E36]
- The operator chart defaults to restricted container settings including non-root, dropped capabilities, no privilege escalation, read-only root filesystem, and seccomp runtime default. [E36]
- Raw manifests can be sourced from the operator repository `config/` tree. [E32, E35]
- Helm-rendered manifests can be sourced from the chart templates if Helm is available in the proposal/implementation environment. [E22, E36]
- The local toolchain currently lacks `helm`. [E37]

## 4. Authentication Model Evidence

### 4.1 Service token

- InfisicalSecret supports `authentication.serviceToken`. [E23, E35]
- Service token auth uses a Kubernetes Secret reference. [E23, E35]
- Service token scope includes `envSlug` and `secretsPath`. [E23, E35]
- The sample service token Secret uses key `infisicalToken`. [E35]
- Service token auth does not show `projectId` in the sample scope. [E23, E35]
- Service token auth is therefore tied to the token's own project/path/environment permissions, based on the CRD sample shape. [E23, E35]
- Service token auth leaves a static token in a Kubernetes Secret. [E23, E35]
- Static token delivery creates a bootstrap chicken-and-egg for GitOps-managed operator sync. [E15, E16, E19, E20, E23]

### 4.2 Universal Auth

- Universal Auth exchanges an identity client ID and client secret at `/api/v1/auth/universal-auth/login`. [E28]
- Universal Auth login returns an access token. [E28]
- Universal Auth access tokens have TTL. [E28]
- Universal Auth default access token TTL is 7200 seconds. [E28]
- Universal Auth docs describe periodic tokens for secret-zero mitigation. [E28]
- Universal Auth can renew access tokens when Access Token Period is set. [E28]
- Universal Auth still requires initial client ID and client secret material. [E28]
- InfisicalSecret supports Universal Auth through a Kubernetes Secret containing `clientId` and `clientSecret`. [E23, E35]
- Universal Auth scope can use `projectId` or `projectSlug`, `envSlug`, and `secretsPath`. [E23, E35]
- Universal Auth maps more directly to a channel schema that wants explicit `project_id`. [E23, E35]
- Universal Auth still leaves initial identity credentials somewhere in cluster bootstrap. [E28, E35]

### 4.3 Kubernetes Auth

- Kubernetes Auth uses a Kubernetes service account JWT. [E29]
- The application sends the JWT to `/api/v1/auth/kubernetes-auth/login`. [E29]
- Infisical validates the JWT through Kubernetes TokenReview. [E29]
- Infisical checks service account name and namespace allowlists. [E29]
- Infisical returns a short-lived access token after successful Kubernetes Auth. [E29]
- Infisical docs recommend clients/SDKs/Agent because they handle service account credential retrieval. [E29]
- Kubernetes Auth can use a central token reviewer JWT or the incoming token itself. [E29]
- If no token reviewer JWT is configured, the client service account needs `system:auth-delegator`. [E29]
- Kubernetes Auth configuration includes Kubernetes API host, allowed service accounts, allowed namespaces, optional audience, CA certificate, token TTL, and max TTL. [E29]
- InfisicalSecret supports Kubernetes Auth with `identityId`, `serviceAccountRef`, and `secretsScope`. [E23, E35]
- Kubernetes Auth reduces static credential material in workload specs, but it requires Infisical instance configuration that trusts the cluster. [E29, E35]
- For a self-hosted local Infisical inside the same k3d cluster, Kubernetes Auth still needs first-run Infisical identity/auth-method setup. [E29, E24]

### 4.4 Authentication fit for per-channel automation

- Per-channel automation needs a server URL. [E20, E23]
- Per-channel automation needs project or project slug identity. [E20, E23]
- Per-channel automation needs environment slug. [E23, E30]
- Per-channel automation needs path/folder scope. [E23, E31]
- Per-channel automation needs a Kubernetes Secret containing service token or Universal Auth credentials, unless Kubernetes Auth is fully configured. [E23, E28, E29, E35]
- Service token is simplest in the Operator CRD shape but creates a static bootstrap secret. [E23, E35]
- Universal Auth carries explicit project scope in the CRD and access-token TTL behavior, but still needs a client secret bootstrap. [E23, E28, E35]
- Kubernetes Auth best matches Kubernetes service identity, but needs machine identity and auth-method setup in Infisical before the Operator can authenticate. [E29, E35]
- The proposal phase must choose an initial auth path with evidence for first-run local bootstrap, not just steady-state reconciliation. [E20, E23, E28, E29, E35]

## 5. Channel Schema Additions Sketch

### 5.1 Current channel schema baseline

- Current channel schema is strict and rejects unknown top-level fields. [E9]
- Current channel schema already supports additive top-level blocks such as `gitops`. [E9, E10]
- Current `gitops` block is optional except when `cluster.target` is `k3d-local`. [E9]
- Current `gitops` block uses required inner fields with no additional properties. [E10]
- Current local channel already carries GitOps endpoint and SOPS bootstrap Secret references. [E7]
- Current dev channel is Vultr-VM-shaped and has no GitOps block yet. [E8]
- Memory says channels carry per-environment provider/endpoint config. [E5, E6]
- D8 says per-channel config carries Infisical endpoint. [E1]

### 5.2 Candidate `infisical` fields supported by evidence

- `server_url` is supported by InfisicalSecret `hostAPI`. [E23, E35]
- `project_id` is supported by InfisicalSecret `secretsScope.projectId` for Universal Auth and several auth methods. [E23, E35]
- `project_slug` is supported by InfisicalSecret `secretsScope.projectSlug`. [E23, E35]
- `environment` or `env_slug` is supported by InfisicalSecret `secretsScope.envSlug`. [E23, E35]
- `secrets_path` is supported by InfisicalSecret `secretsScope.secretsPath`. [E23, E35]
- `recursive` is supported by InfisicalSecret `secretsScope.recursive`. [E23, E35]
- `auth_method` is supported by the CRD's separate auth blocks. [E23, E35]
- `service_token_secret_name` is supported by `serviceTokenSecretReference.secretName`. [E23, E35]
- `service_token_secret_namespace` is supported by `serviceTokenSecretReference.secretNamespace`. [E23, E35]
- `universal_auth_secret_name` is supported by `universalAuth.credentialsRef.secretName`. [E23, E35]
- `universal_auth_secret_namespace` is supported by `universalAuth.credentialsRef.secretNamespace`. [E23, E35]
- `identity_id` is supported by Kubernetes Auth and other identity auth methods. [E23, E29, E35]
- `managed_secret_namespace` is supported by `managedKubeSecretReferences[].secretNamespace`. [E23, E35]
- `managed_secret_name` is supported by `managedKubeSecretReferences[].secretName`. [E23, E35]
- `creation_policy` is supported by `managedKubeSecretReferences[].creationPolicy`. [E23, E35]
- `resync_interval` is supported by `syncConfig.resyncInterval`. [E23, E35]
- `instant_updates` is supported by `syncConfig.instantUpdates`. [E23, E35]
- `ca_secret_name`, `ca_secret_namespace`, and `ca_secret_key` are supported by `tls.caRef`. [E23, E35]

### 5.3 Local versus remote channel evidence

- The local channel must self-host Infisical as a real deployment because D8 says local runs the same components and local is first deployment. [E1, E5]
- The environment-agnostic memory says Infisical instance runs in local cluster and remote cluster. [E5]
- The remote channel is Vultr-locked through D8 and the current `dev` channel shape. [E1, E8]
- The remote `dev` channel is k3s on Vultr VMs, not VKE. [E1, E8]
- The source evidence does not support a remote-only managed Infisical dependency as the default because the memory explicitly says Infisical instance runs in the remote cluster too. [E5]
- The source evidence also notes per-channel endpoint config can differ. [E1, E5, E6]
- DNS and TLS are owned by INIT-105, so INIT-103 local proof may need service/port-forward or cluster-internal URL before public hostname routing exists. [E3, E20, E24]
- The proposal phase must decide whether remote Infisical exposure is cluster-internal until INIT-105 or externally routable later. [E3, E20, E24]
- The research evidence points to a same-distribution self-hosted Infisical path for local and remote, with channel-specific endpoint/exposure config. [E1, E5, E8, E24]

## 6. Local-First Infisical

### 6.1 k3d viability evidence

- Infisical Kubernetes docs support Kubernetes minor release 1.32. [E22]
- The local channel uses k3s version `v1.32.13+k3s1`. [E7]
- Infisical docs list hosted distributions tested, not k3s/k3d. [E22]
- Infisical docs say it may work on other Kubernetes distributions but they are not officially supported. [E22]
- Therefore k3d/k3s is evidence-compatible but not explicitly listed as an officially tested distribution. [E22, E7]
- Infisical Helm docs describe proof-of-concept installs with in-cluster PostgreSQL and Redis. [E24]
- Infisical Helm docs create PVCs for PostgreSQL and Redis. [E24]
- k3d local can support PVC-backed workloads through the Kubernetes storage class available in the local cluster; INIT-103 must verify actual PVC binding in harness. [E7, E24]
- The docs list unbound PVCs as a common pending-Pod cause. [E24]
- The docs do not provide SQLite as a local-only alternative. [E24, E25, E27]
- Local-first therefore means local Postgres/Redis in cluster if the proposal keeps the same self-hosted component set. [E5, E24]

### 6.2 Bootstrap chicken-and-egg

- Infisical server needs initial secrets such as `ENCRYPTION_KEY`, `AUTH_SECRET`, database credentials, Redis URL, and site URL. [E24, E27]
- Infisical Operator needs credentials to read from Infisical. [E23, E28, E29, E35]
- Infisical Operator credentials can be a service token Secret. [E23, E35]
- Infisical Operator credentials can be Universal Auth client credentials Secret. [E23, E28, E35]
- Infisical Operator credentials can be Kubernetes Auth service identity, after Infisical is configured to trust that service account. [E23, E29, E35]
- INIT-102 SOPS channel currently permits only a sentinel encrypted Secret. [E15, E16]
- INIT-102 handoff asks where the Infisical service token enters bootstrap. [E20]
- Any bootstrap path that places Infisical server root secrets or Operator auth credentials in Git must change the SOPS boundary deliberately. [E15, E16, E17]
- Any bootstrap path that creates the token manually must be included in first-run operations and harness assumptions. [E20, E24]
- Any bootstrap path that uses auto-bootstrap must validate the chart's auto-bootstrap behavior and generated Secret format. [E24]
- The chicken-and-egg is not optional because the Operator cannot fetch runtime secrets from Infisical before it can authenticate to Infisical. [E23, E28, E29]

### 6.3 First-run admin and project setup

- Infisical docs say the first user to sign up becomes the instance administrator. [E24]
- Infisical docs say to complete the first signup before exposing Infisical to others. [E24]
- Infisical project docs define a project as a workspace for application secrets. [E30]
- Infisical project docs organize secrets by environments, folders, and individual secrets. [E30]
- Infisical folder docs define folder/path-based storage and nested folders. [E31]
- Operator tutorial describes creating a Machine Identity and a project before using CRDs. [E22]
- Operator tutorial says the operator uses a Machine Identity for Kubernetes Auth. [E22]
- Operator tutorial says the Machine Identity ID is used later in the CRD. [E22]
- Operator tutorial says the project must be created before CRD sync. [E22]
- These docs leave a first-run gap for unattended local GitOps: admin user, organization, project, identity/token, and initial sample secret must exist before final Operator sync can succeed. [E22, E24, E30]

### 6.4 What proves real reconciliation

- INIT-102's real reconciliation proof waits for Flux resources and checks applied cluster state. [E13]
- INIT-103 real reconciliation must include an Infisical server Pod ready state because local done-state requires a real component. [E1, E5]
- INIT-103 real reconciliation must include Operator ready state because INIT-103 scope includes Operator installation. [E3, E19]
- INIT-103 real reconciliation must include an `InfisicalSecret` CR because INIT-103 scope includes CRDs and runtime secret ownership. [E3, E19]
- INIT-103 real reconciliation must include a target Kubernetes Secret created by the Operator, because Infisical docs define Operator delivery that way. [E22, E23]
- A runtime proof Secret should not be `gitops/bootstrap/sops-sentinel.enc.yaml`, because that is the INIT-102 bootstrap sentinel. [E11, E12, E15]
- A runtime proof Secret should be fetched from an Infisical project/environment/path and delivered to a target namespace. [E23, E30, E31]
- Workload auto-reload can be observed later, but a minimal INIT-103 proof can focus on managed Secret sync because workloads are owned later. [E3, E22, E23]

## 7. Boundary Clarity: SOPS vs Infisical

### 7.1 What SOPS owns

- SOPS owns bootstrap-only encrypted manifests. [E1, E12]
- The current bootstrap-only example is `gitops/bootstrap/sops-sentinel.enc.yaml`. [E11, E15, E16]
- Flux uses the age key Secret `sops-age` to decrypt bootstrap-tier manifests. [E7, E12]
- The Flux Git deployment path exists before Infisical runtime sync. [E7, E11, E19]
- The Flux Git deploy key, if introduced for a non-anonymous remote Git source, is bootstrap-tier because Flux needs it before it can reconcile Infisical. [E1, E7, E19]
- The age private key is bootstrap-tier because Flux needs it before it can decrypt bootstrap manifests. [E12, E17]
- Infisical server root configuration secrets are ambiguous at this phase because the server cannot start before those values exist. [E24, E27]
- Operator authentication credentials are ambiguous at this phase because the Operator cannot authenticate before those values exist. [E20, E23]
- The proposal phase must explicitly classify these ambiguous Infisical bootstrap inputs. [E15, E16, E20, E24]

### 7.2 What Infisical owns

- Infisical owns runtime application credentials. [E12]
- Infisical owns Discord tokens. [E12]
- Infisical owns database passwords. [E12]
- Infisical owns API keys. [E12, E15]
- Infisical owns per-channel and per-tenant runtime secrets after the bootstrap boundary. [E1, E3, E12]
- Infisical Operator owns syncing Infisical project data into Kubernetes Secrets. [E22, E23]
- Runtime app workloads should consume Kubernetes Secrets generated by Infisical Operator. [E22, E23]
- Runtime secrets should not be added as SOPS-encrypted Git files. [E11, E12, E15, E16, E19]

### 7.3 Concrete boundary examples

- Flux Git deploy key: SOPS/bootstrap tier, if needed, because Flux needs Git before Infisical can reconcile. [E7, E19]
- Flux age key: SOPS/bootstrap tier because it decrypts bootstrap-only manifests. [E12, E17]
- `gitops-sops-sentinel`: SOPS/bootstrap tier because it proves decryption only. [E11, E12, E17]
- Discord bot token: Infisical/runtime tier. [E12, E15]
- Postgres application password for INIT-111 workloads: Infisical/runtime tier. [E3, E12]
- MinIO credentials for INIT-104: Infisical/runtime tier per dependency ordering. [E3]
- Infisical server `ENCRYPTION_KEY`: bootstrap-classified open question because Infisical needs it before it can run. [E24, E27]
- Infisical server `AUTH_SECRET`: bootstrap-classified open question because Infisical needs it before it can run. [E24, E27]
- Infisical Operator service token: bootstrap-classified open question because Operator needs it before first runtime sync. [E20, E23]
- Infisical Operator Universal Auth client secret: bootstrap-classified open question for the same reason. [E20, E28, E35]

## 8. Toolchain Check

### 8.1 Local command availability

- `infisical`: missing. [E37]
- `tofu`: available, `OpenTofu v1.11.5`. [E37]
- `kubectl`: available, client `v1.34.1`. [E37]
- standalone `kustomize`: missing. [E37]
- `kubectl kustomize`: available. [E37]
- `k3d`: available, `v5.8.3`. [E37]
- `docker`: available, `29.4.0`. [E37]
- `flux`: available, `2.8.6`. [E37]
- `sops`: available, `3.12.2`. [E37]
- `age`: available, `v1.3.1`. [E37]
- `age-keygen`: available, `v1.3.1`. [E37]
- `helm`: missing. [E37]

### 8.2 INIT-102 pinned tool verification

- `infra/scripts/install-cluster-tools.sh --check --no-color` passes for k3d `v5.8.3`. [E37]
- The same script passes for Flux `v2.8.6`. [E37]
- The same script passes for SOPS `v3.12.2`. [E37]
- The same script passes for age `v1.3.1`. [E37]
- The same script passes for age-keygen `v1.3.1`. [E37]
- The INIT-102 tool installer pins k3d, Flux, SOPS, and age versions in script constants. [E13]
- The INIT-102 cluster-mode harness requires Docker, k3d, kubectl, flux, sops, age, and age-keygen. [E13]
- INIT-103 needs to add Infisical CLI and likely Helm or a render-equivalent tool to the toolchain if using chart rendering. [E24, E34, E37]
- Latest Infisical CLI release observed through GitHub API was `v0.43.78`, published 2026-04-24. [E34, E37]
- The local machine does not currently have that CLI installed. [E37]

### 8.3 Toolchain implications for proposal

- Raw Operator manifests can be installed through Flux/Kustomize without Helm at runtime. [E7, E10, E22, E32]
- Helm may still be needed at implementation time to render upstream charts into committed raw manifests. [E22, E24, E36, E37]
- Standalone `kustomize` is missing, but `kubectl kustomize` is present. [E37]
- The proposal must decide whether to vendor rendered YAML, upstream Kustomize config, or Helm-rendered output. [E22, E24, E32, E35, E36]
- The implementation must avoid relying on helm-controller because INIT-102 did not install it. [E11, E19]

## 9. Known Risks and Open Questions

### 9.1 BLOCKS_PROPOSAL

- Authentication path: choose service token, Universal Auth, or Kubernetes Auth for the first local proof. [E20, E23, E28, E29, E35]
- Bootstrap classification: decide how Infisical server root secrets are supplied without violating bootstrap-only SOPS boundaries. [E15, E16, E20, E24, E27]
- Operator credential bootstrap: decide where the service token or identity credential comes from at first install. [E20, E23, E28, E29, E35]
- Project model: decide one project per channel, one project per tenant, or another minimum model for INIT-103. [E20, E30]
- Environment slug mapping: decide how channel exposure/id maps to Infisical `envSlug`. [E6, E23, E30]
- Raw manifest source: decide whether to commit operator repository Kustomize output, Helm-rendered output, or a curated subset. [E22, E32, E35, E36]
- Server install shape: decide whether to render the Infisical Helm chart into raw manifests or author raw manifests from documented image/env/PVC contracts. [E24, E25, E27]
- Operator CRD subset: decide whether INIT-103 installs all six v0.10.32 CRDs or the documented three user-facing CRDs. [E22, E35]
- Operator namespace scope: decide cluster-wide versus namespace-scoped watch/RBAC. [E22, E35, E36]
- Local endpoint before DNS/TLS: decide whether `hostAPI` uses cluster-internal Service URL, port-forward, or a later DNS/TLS handoff. [E3, E20, E23, E24]
- Remote distribution: decide whether remote self-hosts the same Infisical stack inside Vultr k3s, based on environment-agnostic memory. [E1, E5, E8]

### 9.2 BLOCKS_IMPLEMENTATION

- Need install or pin Infisical CLI if scripts create projects, identities, or sample secrets. [E34, E37]
- Need install or pin Helm if implementation renders Helm charts to raw manifests. [E22, E24, E37]
- Need verify exact Infisical server image tag because docs example `v0.151.0` may lag latest releases. [E24, E33]
- Need verify exact Operator image tag because chart version v0.10.32 and values tag v0.10.31 differ. [E32, E36]
- Need verify k3d PVC binding for Infisical PostgreSQL and Redis. [E7, E24]
- Need define namespace layout for server, operator, and target managed Secrets. [E20, E22, E23]
- Need define RBAC minimization if using scoped namespaces. [E22, E35, E36]
- Need define harness assertions for Infisical Pod readiness. [E13, E24]
- Need define harness assertions for Operator readiness. [E13, E22]
- Need define harness assertions for `InfisicalSecret` status/readiness. [E22, E23, E35]
- Need define harness assertions for target Kubernetes Secret content without leaking values to logs. [E12, E15, E23]
- Need update SOPS boundary linter if bootstrap needs more encrypted files. [E15, E16, E17]
- Need update channel schema and resolver tests to include `infisical` inheritance and strictness. [E9, E10, E18]
- Need update GitOps rendering if Infisical manifests are generated from resolved channel YAML. [E7, E10, E18]
- Need document first-run admin/project/identity steps or automate them. [E22, E24, E30]

### 9.3 INFORMATIONAL

- Infisical supports additional auth methods such as AWS IAM, Azure, GCP ID token, GCP IAM, and LDAP in the CRD, but those are not relevant to Vultr/local first proof. [E23, E35]
- Infisical supports dynamic secrets, but INIT-103 can likely prove runtime contract with static secret sync first. [E3, E22, E23]
- Infisical supports managed ConfigMaps, but sensitive runtime values should use managed Secrets. [E23]
- Infisical supports automatic workload reload annotations, but workloads are downstream of INIT-103. [E3, E22, E23]
- Infisical supports SMTP and telemetry configuration, but core secret operations can be evaluated without those being first-order requirements. [E24, E27]
- Infisical docs recommend external managed Postgres and Redis for production HA, but the environment-agnostic memory requires local self-hosting as first deployment. [E5, E24]
- INIT-116 owns full tenant isolation, but INIT-103 still needs a minimal channel/project hierarchy. [E3, E20, E30]
- INIT-105 owns DNS/TLS, but INIT-103 still needs a usable `hostAPI` during local proof. [E3, E23, E24]

## 10. Suggested Slice Decomposition Sketch

- SLICE-103.01: Operator manifest evidence/pinning slice.
- Evidence basis: INIT-103 scope includes Operator, CRDs, and RBAC. [E3]
- Evidence basis: upstream Operator docs and repo provide Helm and raw/Kustomize source material. [E22, E32, E35, E36]
- Evidence basis: INIT-102 GitOps path needs raw manifests under the channel overlay. [E7, E10, E19]

- SLICE-103.02: Infisical server self-hosted manifest evidence/pinning slice.
- Evidence basis: self-hosted Infisical requires application image, Postgres, Redis, and core secrets. [E24, E25, E27]
- Evidence basis: Helm docs provide image, PVC, resource, and readiness examples. [E24]
- Evidence basis: Docker Compose confirms Postgres and Redis dependency shape. [E33]

- SLICE-103.03: Channel schema additions for `infisical`.
- Evidence basis: D8 says channel config carries Infisical endpoint. [E1]
- Evidence basis: existing schema has strict additive top-level `gitops` pattern. [E9, E10]
- Evidence basis: InfisicalSecret requires host/API, project/env/path/auth references. [E23, E35]

- SLICE-103.04: Infisical bootstrap credential path.
- Evidence basis: server root secrets and Operator auth credentials exist before runtime sync. [E24, E27, E23]
- Evidence basis: current SOPS boundary forbids runtime-shaped SOPS secrets. [E15, E16]
- Evidence basis: INIT-102 handoff names service-token bootstrap as an open question. [E20]

- SLICE-103.05: Sample InfisicalSecret CR and managed Kubernetes Secret proof.
- Evidence basis: InfisicalSecret syncs Infisical project/path secrets into Kubernetes Secrets. [E22, E23]
- Evidence basis: managed output uses `managedKubeSecretReferences`. [E23]
- Evidence basis: Phase 5 completion requires Infisical to sync through the Operator. [E4]

- SLICE-103.06: Harness extension.
- Evidence basis: INIT-102 harness already verifies Flux reconciliation and SOPS bootstrap. [E13, E17, E18]
- Evidence basis: INIT-103 handoff asks what readiness assertions extend the harness. [E20]
- Evidence basis: Infisical docs provide status endpoint, Pod readiness, Postgres and Redis checks. [E24]

- SLICE-103.07: Documentation and INIT-104 handoff.
- Evidence basis: INIT-104 depends on INIT-103 for MinIO credentials through Infisical. [E3]
- Evidence basis: INIT-111 and INIT-113 also depend on runtime secret availability. [E3]
- Evidence basis: boundary clarity needs explicit documentation to prevent SOPS-runtime regression. [E11, E12, E15]

## 11. Proposal-Phase Priority Items

- Priority 1: Resolve secret-zero/bootstrap for Infisical server root secrets and Operator auth credentials. [E15, E16, E20, E23, E24, E27]
- Priority 2: Pick the initial Operator auth model for local proof: service token, Universal Auth, or Kubernetes Auth. [E23, E28, E29, E35]
- Priority 3: Choose raw manifest source and version pins for Infisical server and Operator without helm-controller. [E7, E10, E19, E22, E24, E32, E36]

## 12. Evidence-Based Install Shape For Proposal Consideration

- Evidence points to two installed parts: Infisical server plus Infisical Kubernetes Operator. [E3, E22, E24]
- Evidence points to server dependencies: Postgres and Redis. [E24, E25, E27, E33]
- Evidence points to PVC-backed Postgres and Redis for local proof because SQLite is not documented and in-cluster DBs use PVCs. [E24, E25, E27]
- Evidence points to raw committed manifests under `gitops/channels/local/infisical/` because INIT-102 reconciles Kustomize raw manifests and lacks helm-controller. [E7, E10, E19]
- Evidence points to using upstream Helm charts or upstream Kustomize config as source material, then committing rendered/pinned manifests. [E22, E24, E32, E35, E36]
- Evidence points to `InfisicalSecret` as the canonical runtime sync proof, not CLI sync. [E3, E22, E23]
- Evidence points to CLI as dev/bootstrap convenience only, because Kubernetes reconciliation contract is Operator-driven. [E22, E23, E34]
- Evidence points to secret-zero bootstrap as the top proposal issue, not an implementation detail. [E15, E16, E20, E23, E24, E27]

## 13. Remote Vultr Notes

- Remote remains Vultr-locked through D8 and the current `dev` channel. [E1, E8]
- Remote Kubernetes is self-managed k3s on Vultr VMs, not VKE. [E1, E8]
- Environment-agnostic memory says Infisical runs in the remote cluster as the same component as local. [E5]
- Remote `dev` currently has no Flux install path in INIT-102. [E8]
- Remote GitOps installation is therefore outside current substrate done-state and must be handled by successor scope. [E8, E19]
- Remote Infisical external exposure intersects INIT-105 DNS/TLS ownership. [E3]
- Until DNS/TLS exists, the remote evidence supports treating endpoint/exposure as channel config and a later handoff, not a different component. [E1, E5, E6]

## 14. Research Bottom Line

- Current repo has a real local Flux/SOPS bootstrap substrate but no Infisical runtime implementation. [E7, E11, E12]
- Infisical self-hosting requires the Infisical app plus Postgres and Redis. [E24, E25, E27, E33]
- Infisical Operator syncs Infisical project/path data into native Kubernetes Secrets through `InfisicalSecret`. [E22, E23]
- The relevant Operator API group/version is `secrets.infisical.com/v1alpha1`. [E23, E35]
- The minimal local proof should demonstrate Flux applying Infisical resources and Operator-created Kubernetes Secret state. [E4, E13, E22, E23]
- The highest-risk ambiguity is not whether Infisical works; it is how the initial server secrets and Operator auth credentials cross the bootstrap/runtime boundary. [E15, E16, E20, E23, E24, E27]
