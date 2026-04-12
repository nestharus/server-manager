# Base-Application Infrastructure Index

Scope: this index is based on a full read of every file under the requested paths in `.refs/base-application/`: `infrastructure/`, `service/`, `ui/`, `.dagger/`, `.claude/tasks/`, plus the repo `README.md`. Hidden files in scope were included, notably `infrastructure/.gitignore` and `service/platform-service/terraform/.env.example`. Binary files in scope were also inspected at metadata level: `infrastructure/infrastructure diagram.jpeg` and `service/user-service/gradle/wrapper/gradle-wrapper.jar`.

The key conclusion is that this repo is not one clean platform implementation. It is three overlapping layers:

1. An older, more executable Terraform plus Ansible bootstrap centered in `service/platform-service/terraform/`.
2. A newer, more ambitious Crossplane plus Flux multi-cluster model in `infrastructure/`.
3. A local Dagger simulation layer plus examples and stubs around those two.

That overlap matters. The older layer is the closest thing to a runnable bootstrap. The newer layer is the clearer statement of intended architecture. The repo’s value as a template is therefore structural and conceptual, not “apply this tree as-is.”

## 1. Executive summary

`base-application` is a reference repo for a Vultr-hosted Kubernetes platform with a dedicated platform cluster and multiple application clusters. The intended steady-state model is:

- Terraform brings up base cloud resources.
- Ansible performs imperative bootstrap on fresh clusters.
- Crossplane turns cluster claims into Vultr VKE clusters and supporting cloud objects.
- Flux continuously reconciles platform resources, application-cluster claims, and service manifests.
- Helm installs shared infrastructure services such as Kong and JFrog Artifactory.
- Raw Kustomize manifests deploy application services such as `user-service`.

At the documentation level, the platform is supposed to support four environment types:

- `dev`: persistent, low-cost, shared services.
- `staging`: production-shaped, dedicated services.
- `prod`: production, dedicated services.
- `sue`: ephemeral “system under evaluation,” shared services, 24-hour lifetime.

At the repository level, only part of that model exists. The actual repo contains one concrete application (`user-service`), one concrete bootstrap toolchain (`platform-service/terraform` plus Ansible playbooks), a concrete Kong deployment, a concrete JFrog manifest set, and concrete Crossplane and Flux objects for cluster claims. It does not contain working implementations for many of the services claimed in the README and task plan: no `infrastructure/infisical/`, no `monitoring/`, no `cloudflare/`, no `opal-cedar/`, no `authentik/`, no `gitlab-ci/`, no `elasticsearch/`, and no non-empty UI implementation.

The most important structural insight is that the repo has already undergone a migration that stopped halfway:

- `service/platform-service/terraform/` is the older “bootstrap by Terraform null_resource and Ansible” model.
- `infrastructure/` is the newer “bootstrap platform, then let Crossplane and Flux manage the rest” model.
- The root `README.md` is effectively a future-work scratchpad, not a repo guide.

That means the canonical pattern to reuse is not any single file. It is the layering:

- cloud primitives in Terraform,
- cluster bootstrap in Ansible,
- cloud abstraction in Crossplane,
- continuous reconciliation in Flux,
- infra services by Helm,
- app services by Kustomize,
- environment shape encoded separately from service manifests.

## 2. Architecture layers

### The repo’s actual architecture layers

There are two bootstrap chains in the repo, plus one simulation chain.

### Chain A: older executable bootstrap

This chain lives under `service/platform-service/terraform/` and is the most internally coherent part of the repo.

1. `backend.tf` stores state in Vultr Object Storage via the S3 backend.
2. `network/main.tf` creates a Vultr VPC.
3. `kubernetes/main.tf` creates a VKE cluster with two node pools, writes a kubeconfig, writes an Ansible inventory, labels nodes, and runs `kubernetes-setup.yml`.
4. The root Terraform module then triggers, in order:
   - `playbook/crossplane.yml`
   - `playbook/infisical.yml`
   - `playbook/flux.yml`
   - `playbook/minio.yml`
5. After that, the intended platform would be ready for GitOps and services.

This is a “Terraform orchestrates imperative bootstrap” design. It is not pure GitOps, but it is concrete.

### Chain B: newer intended multi-cluster GitOps bootstrap

This chain lives under `infrastructure/` and expresses the architecture the repo wants to become.

1. `infrastructure/platform.tf` is supposed to create the platform VPC and platform VKE cluster.
2. The platform cluster gets Crossplane and Flux installed by Ansible playbooks.
3. `platform-flux-system/` then applies:
   - Crossplane providers
   - Crossplane XRDs
   - Crossplane compositions
   - platform services such as JFrog and Infisical
4. `flux-system/application-clusters.yaml` applies `infrastructure/clusters/`, which contains:
   - environment type ConfigMaps
   - concrete `KubernetesCluster` claims
   - per-environment Flux bootstrap `Kustomization` objects
5. Crossplane provisions application clusters from those claims.
6. Child Flux instances bootstrap onto those application clusters.
7. Child Flux instances reconcile application-cluster infrastructure and app manifests such as Kong and `user-service`.

This is the architecture the repo documents most heavily. It is also the architecture with the most breakage and missing pieces.

### Chain C: local simulation layer

This lives under `.dagger/` and is a Docker-in-Docker approximation of the intended platform:

- one “platform” container,
- one “environment” container,
- container-mode Ansible playbooks,
- ad hoc container deployments for Infisical, JFrog, and Kong.

This is not the real control path. It is a local test/demo path.

### What bootstraps what

Observed bootstrap order across the repo:

- Terraform bootstraps VPC and Kubernetes clusters.
- Terraform `local_file` resources bootstrap kubeconfig and inventory.
- Ansible bootstraps base cluster conventions, namespaces, priority classes, node labels, Crossplane, Flux, Infisical, and MinIO.
- Crossplane is supposed to bootstrap new application clusters from `KubernetesCluster` claims.
- Flux is supposed to bootstrap manifests onto both the platform cluster and child clusters.
- Helm installs infrastructure services such as Kong and JFrog.
- Raw manifests plus Kustomize install app services such as `user-service`.

### What manages what

- Terraform manages Vultr VPCs, VKE clusters, local kubeconfig files, and imperative post-create hooks.
- Ansible manages first-boot cluster setup and several Helm-based installs.
- Crossplane is intended to manage cloud infrastructure from in-cluster claims, especially VPCs and application clusters.
- Flux manages Git sources, Kustomizations, platform services, cluster claims, and service manifests.
- Helm manages Kong and Artifactory, and in the older path also Infisical and MinIO.
- Kustomize manages raw service manifests, namespace scaffolding, and environment bootstrap overlays.

### Platform cluster vs application cluster boundary

The intended boundary is clear even when the implementation is incomplete.

Platform cluster responsibilities:

- Crossplane control plane
- Flux control plane
- shared secrets management
- shared artifact registry
- shared object storage / claim store
- shared auth, logging, monitoring, and policy services for `dev` and `sue`

Application cluster responsibilities:

- team or environment-specific workloads
- Kong ingress/gateway for that environment
- app services such as `user-service`
- environment-specific Flux instance
- dedicated shared services for `staging` and `prod` according to docs

What is actually implemented on disk:

- platform cluster: Crossplane and Flux playbooks exist; JFrog manifests exist; Infisical and MinIO exist as Ansible playbooks, not platform Flux manifests.
- application clusters: Crossplane claim objects exist; Flux bootstrap objects exist; Kong manifests exist; `user-service` manifests exist.
- dedicated `staging`/`prod` shared-service isolation exists only in docs and planning, not as concrete manifests.

## 3. Component inventory

Status is conservative:

- `complete`: materially implemented and internally coherent as a template unit.
- `stub`: non-empty implementation exists, but it is incomplete, broken, placeholder-heavy, or mismatched with adjacent layers.
- `readme-only`: the repo only names the thing or leaves empty files.

| Component | Location in repo | Role | Managed by | Status |
|---|---|---|---|---|
| Root README scratchpad | `README.md` | Future notes about env vars, Flagsmith/Infisical, and Flux watching S3 claims | Human | readme-only |
| Platform Terraform root | `infrastructure/platform.tf` | Intended platform-cluster bootstrap in the new architecture | Terraform + local-exec Ansible | stub |
| Infrastructure base playbooks | `infrastructure/playbooks/*.yml` | Base cluster setup, Crossplane/Flux install, platform setup, container-mode variants | Ansible | complete |
| Environment type model | `infrastructure/clusters/environment-types/*.yaml` | Encodes `dev`, `staging`, `prod`, `sue` node-pool and feature profiles | Flux + ConfigMaps | stub |
| Environment claims/examples | `infrastructure/clusters/environments/*.yaml` | Example `KubernetesCluster` claims plus child-cluster bootstrap objects | Flux -> Crossplane | stub |
| Cluster template | `infrastructure/clusters/cluster-template.yaml` | Parameterized cluster-claim plus child Flux bootstrap pattern | Flux + Kustomize | stub |
| Cluster bootstrap overlay | `infrastructure/clusters/bootstrap/*` | Bootstraps child `flux-system` namespace, GitRepository, and SecretStore | Flux | stub |
| Crossplane provider config | `infrastructure/crossplane/providers/provider-vultr.yaml` | Installs Vultr provider and `ProviderConfig` | Flux -> Crossplane | stub |
| Crossplane XRD | `infrastructure/crossplane/xrds/kubernetes-cluster.yaml` | Defines `KubernetesCluster` claim schema | Flux -> Crossplane | stub |
| Crossplane composition | `infrastructure/crossplane/compositions/kubernetes-cluster.yaml` | Maps cluster claims to Vultr VPC, VKE cluster, node pools, kubeconfig secret | Flux -> Crossplane | stub |
| Platform Flux root | `infrastructure/platform-flux-system/*` | Applies platform services and Crossplane resources from the platform cluster | Flux | stub |
| Application Flux root | `infrastructure/flux-system/*` | Applies infra sync, Kong, app-cluster claims, image automation, and user-service source | Flux | stub |
| Kong stack | `infrastructure/kong/*` | Shared or per-environment API gateway via HelmRelease, plugins, Ingress, and config job | Flux + Helm + raw manifests | stub |
| JFrog Artifactory stack | `infrastructure/jfrog-artifactory/*` | Docker/OCI registry on the platform cluster | Flux + Helm | stub |
| Deprecated node-pool reference | `infrastructure/node-pools.yaml` | Comment-only reference for historical node-pool taxonomy | Human | readme-only |
| Platform-service Terraform root | `service/platform-service/terraform/main.tf` | Executable bootstrap chain for VPC, VKE, and post-create playbooks | Terraform | complete |
| Terraform S3 backend config | `service/platform-service/terraform/backend.tf` | Stores Terraform state in Vultr Object Storage | Terraform | complete |
| Terraform network module | `service/platform-service/terraform/network/*` | Creates the platform VPC | Terraform | complete |
| Terraform Kubernetes module | `service/platform-service/terraform/kubernetes/*` | Creates VKE cluster, kubeconfig, inventory, labels, and base setup | Terraform + Ansible | complete |
| Platform-service Crossplane playbook | `service/platform-service/terraform/playbook/crossplane.yml` | Installs Crossplane into the bootstrap cluster | Ansible + Helm | complete |
| Platform-service Flux playbook | `service/platform-service/terraform/playbook/flux.yml` | Installs Flux and patches controllers for Infisical auth | Ansible + Helm | stub |
| Platform-service Infisical playbook | `service/platform-service/terraform/playbook/infisical.yml` | Deploys and bootstraps Infisical with Kubernetes auth ideas | Ansible + Helm + REST init | stub |
| Platform-service MinIO playbook | `service/platform-service/terraform/playbook/minio.yml` | Deploys MinIO, secret sync, and a Crossplane PVC abstraction | Ansible + Helm + Jobs | stub |
| Platform-service README/infra placeholder | `service/platform-service/README.md`, `service/platform-service/infrastructure/main.yml` | Describes platform service usage, but runtime deploy file is empty | Human | readme-only |
| Platform-service example app/HPA | `service/platform-service/example/application/*` | Example raw K8s deployment and autoscaler | Human/examples | complete |
| Platform-service secret subscriber examples | `service/platform-service/example/secret/*` | Most fleshed-out service integration pattern: Infisical K8s auth with webhook updates | Human/examples | complete |
| Platform-service Flink task examples | `service/platform-service/example/task/*`, `notes.txt` | Example async task workers and stray scaling note | Human/examples | complete |
| Auth service | `service/auth-service/*` | Intended Authentik + OPAL auth service | Human | readme-only |
| AI service | `service/ai-service/README.md` | Names ontology and agent-management concerns | Human | readme-only |
| Invoice service | `service/invoice-service/README.md` | Names transactions/payments/invoices concern | Human | readme-only |
| Message service | `service/message-service/README.md` | Names notifications/email/chat/SNS/toaster concern | Human | readme-only |
| Search service | `service/search-service/README.md` | Placeholder directory with empty README | Human | readme-only |
| User-service codebase | `service/user-service/src/main/java/**`, `src/main/resources/db/schema/**` | Java/Vert.x/Geldata service skeleton and schema | Gradle | stub |
| User-service infra manifests | `service/user-service/src/main/resources/infrastructure/*` | Namespace, deployment, service, HPA, config, network policy | Flux + Kustomize | complete |
| User-service build toolchain | `service/user-service/build.gradle`, `gradle/**`, `gradlew*` | Gradle wrapper, conventions, Java 24 build | Gradle | complete |
| Dagger pipeline | `.dagger/**` | Local containerized simulation of platform and env services | Dagger + Ansible in container mode | stub |
| Mobile UI | `ui/mobile/README.md` | Placeholder for UI/mobile structure | Human | readme-only |
| Claude task plan | `.claude/tasks/infrastructure-implementation-plan.md` | Giant implementation roadmap for the intended target platform | Human/planning | readme-only |

## 4. Crossplane pattern

The Crossplane pattern is narrow but clear: define one cluster claim type, map that claim to Vultr primitives, and let Flux create those claims from Git-managed environment definitions.

### XRDs

There is one XRD:

- `infrastructure/crossplane/xrds/kubernetes-cluster.yaml`

It defines:

- composite kind: `XKubernetesCluster`
- claim kind: `KubernetesCluster`
- parameters:
  - `region`
  - `version`
  - `clusterType`
  - `environmentName`
  - `environmentType`
  - `enableHA`
  - `nodePools`
- status fields:
  - `clusterEndpoint`
  - `clusterID`
  - `vpcID`

This is the central contract of the newer architecture. Everything else in `infrastructure/clusters/` assumes this claim exists.

### Compositions

There is one composition:

- `infrastructure/crossplane/compositions/kubernetes-cluster.yaml`

It maps one `KubernetesCluster` claim to:

1. a Vultr `VPC`
2. a Vultr `Kubernetes` cluster
3. a `general-restricted` node pool
4. a `general-public` node pool
5. a `Secret` object intended to hold kubeconfig material

Observed mapping rules:

- `clusterType=platform` vs `application` changes VPC subnet and `general-restricted` max size.
- cluster label is generated from `environmentName`.
- `enableHA` maps onto Vultr control-plane HA.

Important limitation: the composition does **not** consume the `nodePools` array from the XRD, even though the XRD and environment type ConfigMaps imply that it should. The environment type model therefore exists on paper but is not actually wired into cluster provisioning.

### Provider configuration

`infrastructure/crossplane/providers/provider-vultr.yaml` installs:

- `Provider` `provider-vultr`
- `ControllerConfig` `vultr-config`
- `ProviderConfig` `default`

The provider expects a secret:

- name: `vultr-credentials`
- namespace: `crossplane-system`
- key: `api-key`

That is a standard pattern: provider package plus secret-based credentials plus a default provider config.

### How Flux watches cluster CRDs and Crossplane provisions them

The repo’s intended control loop is:

1. `platform-flux-system/crossplane-resources.yaml` applies providers.
2. It then applies XRDs.
3. It then applies compositions.
4. `flux-system/application-clusters.yaml` applies `infrastructure/clusters/`.
5. The files under `infrastructure/clusters/environments/` create `KubernetesCluster` claims.
6. Crossplane reconciles those claims into Vultr resources.
7. The paired Flux `Kustomization` object in each environment file bootstraps the child cluster.

This is the canonical Crossplane plus Flux pattern the repo is trying to establish.

### Crossplane gaps

The current implementation has several critical breaks:

- The composition references `providerConfigRef.name: kubernetes-provider` for the kubeconfig `Object`, but no such provider config exists anywhere in the repo.
- The composition creates the kubeconfig secret name from `metadata.uid`, while child-cluster bootstrap expects a secret named `${environment_name}-cluster-kubeconfig`.
- The composition does not wire connection details from the Vultr `Kubernetes` resource into that secret.
- The `platform-cluster` claim is namespaced to `platform-flux-system`, but the bootstrap playbooks create `flux-system`, not `platform-flux-system`.
- The XRD supports `nodePools`, but the composition ignores them.

So the pattern is clear, but the multicluster Crossplane path is not complete enough to work end to end.

## 5. Flux pattern

Flux is the repo’s steady-state control plane, and the directory structure shows how the author expects reconciliation to be split.

### Repository structure

There are three Flux-related roots:

- `infrastructure/platform-flux-system/`: platform-cluster Flux objects
- `infrastructure/flux-system/`: application-cluster Flux objects
- `infrastructure/clusters/bootstrap/`: payload used to bootstrap child clusters

This is the correct shape for a multi-cluster GitOps repo: separate the platform control plane, application cluster control plane, and child bootstrap payload.

### Multi-cluster management

The intended pattern is:

- platform Flux applies Crossplane resources and platform services
- platform Flux also applies `KubernetesCluster` claims for application clusters
- Crossplane provisions those clusters
- per-environment `Kustomization` objects use remote `kubeConfig.secretRef` to bootstrap Flux into those child clusters
- child Flux instances then reconcile infrastructure and services against themselves

This is visible in:

- `platform-flux-system/crossplane-resources.yaml`
- `flux-system/application-clusters.yaml`
- `clusters/cluster-template.yaml`
- `clusters/environments/*.yaml`

### Kustomization hierarchy

Observed hierarchy:

- `platform-flux-system/kustomization.yaml`
  - `platform-sync.yaml`
  - `crossplane-resources.yaml`
  - `platform-cluster.yaml`

- `flux-system/kustomization.yaml`
  - `infrastructure-sync.yaml`
  - `node-pools-sync.yaml` (missing)
  - `user-service-source.yaml`
  - `image-automation.yaml`
  - `application-clusters.yaml`

- `clusters/bootstrap/kustomization.yaml`
  - patches child-cluster `flux-system` Kustomization to add a required secret substitution source

This is a sound hierarchy in design terms: parent cluster manages child cluster definitions; child cluster manages local infra and apps.

### Health checks and dependencies

Flux dependencies exist in several places:

- `crossplane-xrds` depends on `crossplane-providers`
- `crossplane-compositions` depends on `crossplane-xrds`
- environment bootstrap Kustomizations depend on `application-clusters`
- `kong` depends on `infrastructure`
- `user-service-infrastructure` depends on `infrastructure` and `crossplane-system`

Flux health checks are also used, but some are clearly wrong:

- `application-clusters.yaml` health-checks hardcoded `dev-cluster`, `staging-cluster`, `prod-cluster`, and `sue-cluster`, while the actual examples are `dev-team1-cluster` and `prod-main-cluster`.
- `platform-sync.yaml` health-checks `Deployment/infisical`, but there is no `infrastructure/infisical/` directory.

### Image automation

The image automation pattern is standard Flux:

- `ImageRepository` points at `jcr.example.com/base-application/user-service`
- `ImagePolicy` selects semver `>=1.0.0`
- `ImageUpdateAutomation` commits back to Git using setters

The service manifest includes the expected Flux setter comment:

- `image: jcr.example.com/base-application/user-service:latest # {"$imagepolicy": "flux-system:user-service"}`

The bug is pathing:

- Flux points at `./services/user-service/...`
- the actual repo path is `./service/user-service/...`

That same `service` vs `services` mismatch appears in both `user-service-source.yaml` and `image-automation.yaml`.

### Flux gaps

The biggest issues in the Flux layer are:

- missing `node-pools-sync.yaml`
- missing `infrastructure/infisical/`
- missing `services/` path used by user-service sync and image automation
- child bootstrap depends on secrets and external CRDs that are not installed in-repo
- the repo mixes namespace `flux-system` and `platform-flux-system` inconsistently

So the Flux pattern is strong as a template, but the checked-in tree is not internally consistent.

## 6. Environment model

The environment model is one of the strongest conceptual parts of the repo.

### Defined environments

Four environment types are defined:

- `dev`
- `staging`
- `prod`
- `sue`

Each one has a ConfigMap under `infrastructure/clusters/environment-types/`.

Each ConfigMap encodes:

- HA on/off
- enabled node pools
- node counts and autoscaling bounds
- plan sizes
- labels and taints
- coarse feature flags like `monitoring`, `backup`, and `costOptimization`

Examples:

- `dev`: `general-restricted`, `general-public`, `spot`; HA off; aggressive autoscaling
- `staging`: `general-restricted`, `general-public`, `memory`; HA on
- `prod`: `general-restricted`, `general-public`, `memory`, `storage`, `ai`; HA on
- `sue`: `general-restricted`, `general-public`, `spot`; HA off; maximum cost optimization

### Cluster template with variable substitution

`infrastructure/clusters/cluster-template.yaml` contains the environment-cluster template. It substitutes:

- `environment_name`
- `environment_type`
- `vultr_region`
- `kubernetes_version`

It also contains the paired child-cluster Flux bootstrap object. That bootstrap uses:

- direct `postBuild.substitute`
- `substituteFrom` a secret and environment-type ConfigMap

So the intended pattern is:

- one claim per environment
- one Flux bootstrap per environment
- environment-specific values injected at bootstrap time

### Concrete environments present

Only two example environment files exist:

- `dev-team1.yaml`
- `prod-main.yaml`

There are no checked-in `staging` or `sue` environment examples. Those environment types exist only as ConfigMaps and documentation.

### Shared on platform vs dedicated per environment

The README and task plan are explicit:

- `dev` and `sue` are supposed to use shared platform-cluster services.
- `staging` and `prod` are supposed to get dedicated Elasticsearch, Kong, OPAL/Cedar, and monitoring stacks, plus Cloudflare WAF.

What actually exists:

- platform shared services on disk: JFrog manifests, plus Infisical and MinIO in the older Terraform/Ansible path
- dedicated environment services on disk: Kong manifests and `user-service` manifests, but no dedicated Elasticsearch, monitoring, OPAL/Cedar, or Cloudflare manifests

### Environment model gaps

The environment model is more advanced than the provisioning layer that is supposed to enforce it.

The specific breaks are:

- the XRD/composition path does not consume environment-type node-pool definitions
- there is no TTL or expiration controller for `sue`
- there is no implementation of the dedicated stage/prod service stacks described in the docs
- `staging` exists as a type but not as a concrete environment example

So the environment model is best understood as an architecture contract, not a fully encoded system.

## 7. Service patterns

### How services are deployed

The repo uses three service-deployment styles:

1. `HelmRelease` under Flux for infrastructure products:
   - Kong
   - JFrog Artifactory

2. Raw manifests plus Kustomize for application services:
   - `user-service`

3. Terraform plus Ansible plus Helm for bootstrap/platform services in the older stack:
   - Crossplane
   - Flux
   - Infisical
   - MinIO

This mixed mode is not accidental. It reflects the author’s distinction between:

- cluster bootstrapping,
- shared infrastructure products,
- ordinary application workloads.

### Auth service pattern: Authentik + OPAL

The intended auth-service stack is visible only as naming:

- `service/auth-service/README.md` says `authentication` and `authorization`
- `service/auth-service/authentik.yml` is empty
- `service/auth-service/opal.yml` is empty

The broader auth design appears elsewhere:

- the task plan describes Authentik and OPAL/Cedar in detail
- the platform-service secret examples describe Infisical-backed Kubernetes auth

So the repo’s auth pattern is conceptually:

- Authentik for identity/authentication
- OPAL/Cedar for authorization
- Infisical for service secret delivery

But only the Infisical example layer is fleshed out.

### Platform service pattern

`platform-service` is not a deployed application service in the current repo. It is a platform bootstrap toolkit plus examples.

Evidence:

- `service/platform-service/README.md` says `ci/cd`, `environment management`, `root infrastructure`, `repository management`, `events`
- it tells the operator to run Terraform and an infrastructure file
- `service/platform-service/infrastructure/main.yml` is empty
- there is no runtime code directory for a platform API

The platform-service therefore acts more like an ops bundle than a service.

### Kong configuration pattern

Kong is the clearest shared infra product pattern on disk.

Pattern:

- install Kong by Flux `HelmRelease`
- include bundled PostgreSQL subchart
- run on `general-public` nodes
- expose proxy via Vultr load balancer
- create routing with Kubernetes `Ingress`
- create plugins with `KongPlugin`
- optionally also run an imperative `Job` that configures Kong through the Admin API

That last bullet is important. The repo uses **both** declarative Kong CRDs and an imperative curl-based config job. That means the intended Kong pattern is mixed-mode. It works as a proof of concept, but it is not a clean steady-state pattern.

### User-service pattern

`user-service` is the only concrete app service in the repo.

Application stack:

- Java 24
- Vert.x
- Dagger
- Geldata driver
- SLF4J

Infrastructure stack:

- namespace manifest
- deployment manifest
- service manifest
- HPA
- network policy
- config via `configMapGenerator`

The build is concrete, but the runtime logic is still a skeleton:

- `Server.java` only initializes Dagger and Vert.x
- `UserService.java` is commented-out exploratory code
- schema files define a `User` type extending `AbstractRecord`
- deployment expects DB credentials in `Secret/user-service-db`, but no DB provisioning exists in-repo

So the service pattern is real, but the app implementation is partial.

### Platform-service example patterns

The `platform-service/example/secret/` directory is more mature than many of the core service directories. It shows a strong intended pattern for service secret delivery:

- Kubernetes native auth to Infisical
- no long-lived machine tokens
- initial secret load once
- webhook-driven updates, not polling
- token auto-renewal

That example exists in both Python and Java and is accompanied by a long explanatory README. It should be treated as a reference pattern library, not as deployed code.

## 8. What’s complete vs stub

### Most complete and reusable patterns

- `service/platform-service/terraform/network/` and `service/platform-service/terraform/kubernetes/` are the most coherent infra modules in the repo.
- `infrastructure/playbooks/{kubernetes-setup,crossplane,flux,platform-setup}.yml` are reusable bootstrap patterns even if the broader repo is in flux.
- `service/user-service/src/main/resources/infrastructure/` is a solid example of how a service should package its deployment manifests for Flux plus Kustomize.
- `service/platform-service/example/secret/` is the most mature service integration reference in the repo.
- `.dagger/src/pipeline/main.py` is a usable local-simulation prototype, though it is not the real control plane.

### Stubbed or internally inconsistent areas

- `infrastructure/platform.tf` is incomplete: it references undeclared variables and a missing `vultr_vpc.kubernetes`.
- the Crossplane composition does not actually implement the environment-type node-pool model.
- the child-cluster kubeconfig secret path is broken by name mismatch and missing provider wiring.
- `infrastructure/flux-system/kustomization.yaml` references missing `node-pools-sync.yaml`.
- `platform-flux-system/platform-sync.yaml` references missing `infrastructure/infisical/`.
- Flux paths for `user-service` use `services/` instead of `service/`.
- `application-clusters.yaml` health checks target non-existent cluster names.
- Kong is configured both declaratively and imperatively.
- JFrog Artifactory manifests rely on placeholders, hardcoded credentials, and a manual license secret.
- Infisical and MinIO playbooks are extensive but still feel like bootstrap experiments rather than stable platform building blocks.

### Readme-only or near-empty areas

- `service/ai-service/`
- `service/invoice-service/`
- `service/message-service/`
- `service/search-service/`
- `service/auth-service/`
- `service/README.md`
- `service/user-service/README.md`
- `ui/mobile/README.md`

### A useful way to interpret the repo

If this repo is treated as “production-ready infra,” it will disappoint. If it is treated as “canonical pattern vocabulary,” it is valuable. The reusable patterns are:

- separate platform and application cluster concerns
- encode environment type independently from service manifests
- use Flux for steady-state drift correction
- use Crossplane claims as the bridge between environment intent and cloud resources
- let services own their own infra manifests

## 9. What needs modernization

### Dagger -> Buildkite

This one is already effectively decided outside the reference repo. Current local project planning in `plans/proposals/phase1-foundation-v2.md` and related research/risk artifacts assumes Buildkite as the CI direction and treats Buildkite agents as a later consumer of the platform. The Dagger layer in `base-application` is a local Docker-in-Docker simulator, not a production control path.

Recommendation:

- retire Dagger as the canonical automation layer
- keep only the idea of “local simulation” if still useful
- move real automation to Buildkite jobs that run OpenTofu/Flux validation and cluster smoke tests

### JFrog Artifactory -> Harbor?

There is **no checked-in local project decision** in this checkout that explicitly selects Harbor. The only local mention is in a risk note describing “future Harbor” as a Phase 2 consumer, not a ratified platform choice.

What is clear is that the current JFrog pattern is outdated and unsafe as written:

- placeholder license secret
- `admin/changeme` style credentials
- bootstrap curl against `admin:password`
- Dagger pipeline uses `docker.bintray.io/jfrog/artifactory-jcr`, which is a sunset-era registry hostname

So the modernization conclusion is:

- registry modernization is required
- Harbor is plausible, but not yet a checked-in decision here
- if JFrog is kept, the implementation still needs a full refresh
- if Harbor is chosen later, treat that as replacement, not incremental cleanup

### MinIO -> Vultr Object Storage

Current local project planning already assumes Vultr Object Storage for Terraform state and artifact storage. The older `platform-service/terraform/backend.tf` also already uses Vultr Object Storage for state.

That makes the MinIO design in `base-application` look heavy:

- self-hosted MinIO on the cluster
- Infisical-managed credentials
- CronJob-based secret sync
- separate Crossplane PVC abstraction

Unless the platform truly needs self-hosted S3 semantics inside the cluster, Vultr Object Storage is the cleaner default. The base-app repo’s MinIO pattern should therefore be treated as optional or legacy.

### Ansible playbooks -> what replaces them

There is **no checked-in local decision artifact** in this checkout that explicitly says “replace Ansible with X.” But the current local platform work is clearly moving toward:

- OpenTofu for infrastructure provisioning
- Flux for reconciliation
- Buildkite for pipeline execution

In `base-application`, Ansible is doing several jobs:

- first-boot cluster configuration
- Helm installs for core services
- imperative REST initialization
- token/bootstrap side effects
- container-mode simulation for Dagger

That is too much imperative logic for a long-term GitOps platform. The likely replacements are split by concern:

- OpenTofu for cloud resource creation
- Flux plus HelmRelease plus Kustomize for steady-state installs
- CI jobs for one-time bootstrap actions
- controller/operator logic for credential and token propagation, where still needed

### Other outdated elements

- `Terraform` rather than `OpenTofu`: current local platform planning already centers OpenTofu, so the reference repo’s Terraform naming is behind current direction.
- mixed Infisical annotation domains: the repo uses both `infisical.io/*` and `infisical.com/*`.
- `external-secrets.io/v1beta1 SecretStore` is referenced in child bootstrap, but no External Secrets operator is installed anywhere in repo.
- `sops` decryption is configured for `user-service`, but there is no `sops-age` secret or other SOPS bootstrap in the repo.
- `node-pools.yaml` is marked deprecated while `flux-system/kustomization.yaml` still references a missing `node-pools-sync.yaml`.
- the root README mentions Flux watching S3 buckets for SUE deployments, but there is no implementation of that watcher flow.

## 10. Dependency graph

Because the repo has two overlapping bootstrap models, the cleanest way to describe dependencies is as two graphs.

### Graph A: most executable bootstrap sequence in the repo

This is the sequence implied by `service/platform-service/terraform/`.

1. Operator exports Vultr API key and Vultr Object Storage credentials from `.env.example`.
2. Terraform initializes remote state in Vultr Object Storage via `backend.tf`.
3. Terraform applies `network/main.tf` to create the VPC.
4. Terraform applies `kubernetes/main.tf` to create the VKE cluster with system and application node pools.
5. Terraform writes kubeconfig and Ansible inventory locally.
6. Terraform runs `kubernetes/kubernetes-setup.yml` to label nodes, taint system nodes, create priority classes, and create base namespace scaffolding.
7. Terraform runs `playbook/crossplane.yml` to install Crossplane.
8. Terraform runs `playbook/infisical.yml` to deploy Infisical and initialize identities.
9. Terraform runs `playbook/flux.yml` to install Flux and patch controllers for Infisical auth.
10. Terraform runs `playbook/minio.yml` to deploy MinIO and its supporting sync jobs.
11. Flux and/or operators then deploy higher-level infrastructure and application services.

This is the only end-to-end bootstrap sequence in the repo that is close to self-contained.

### Graph B: intended steady-state multi-cluster sequence

This is the sequence implied by `infrastructure/`.

1. Create the platform cluster.
2. Install Crossplane and Flux on the platform cluster.
3. Flux applies Crossplane provider, XRD, and composition objects from `platform-flux-system/crossplane-resources.yaml`.
4. Flux applies platform services from `platform-sync.yaml`.
5. Flux applies application cluster claims and bootstrap Kustomizations from `flux-system/application-clusters.yaml`.
6. Crossplane provisions application-cluster VPCs and VKE clusters.
7. Crossplane writes kubeconfig secrets for those clusters.
8. Per-environment Flux bootstrap Kustomizations reconcile `clusters/bootstrap/` onto the child clusters.
9. Child Flux instances reconcile:
   - `infrastructure/`
   - `infrastructure/kong/`
   - service manifests such as `service/user-service/src/main/resources/infrastructure/`
10. Kong exposes routes to app services.
11. Flux image automation updates app manifests as new JCR images appear.

### Where the dependency graph currently breaks

The intended sequence currently fails at several edges:

- step 1 in Graph B is incomplete because `infrastructure/platform.tf` is not self-contained
- step 4 is incomplete because `platform-sync.yaml` points at missing `infrastructure/infisical/`
- step 7 is incomplete because kubeconfig secret generation is not wired correctly
- step 9 is incomplete because user-service sync points at the wrong repo path

That is why the repo should be treated as a template to decompose, not a system to reuse unchanged.

## 11. Raw statistics

Counts below are for the required read scope only.

- Files read: 123
  - `infrastructure/`: 47 files
  - `service/`: 67 files
  - `ui/`: 1 file
  - `.dagger/`: 6 files
  - `.claude/tasks/`: 1 file
  - repo `README.md`: 1 file
- YAML/YML files: 56
  - `infrastructure/`: 40
  - `service/`: 16
- Kubernetes manifest documents: 70 total `kind:` documents across the YAML/YML files
- Terraform files: 5
  - `infrastructure/platform.tf`
  - `service/platform-service/terraform/backend.tf`
  - `service/platform-service/terraform/main.tf`
  - `service/platform-service/terraform/network/main.tf`
  - `service/platform-service/terraform/kubernetes/main.tf`
- Playbook files: 13
  - 8 under `infrastructure/playbooks/`
  - 4 under `service/platform-service/terraform/playbook/`
  - 1 under `service/platform-service/terraform/kubernetes/`
- Top-level service directories: 7
  - `ai-service`
  - `auth-service`
  - `invoice-service`
  - `message-service`
  - `platform-service`
  - `search-service`
  - `user-service`
- Empty files in scope: 7
  - `service/README.md`
  - `service/auth-service/authentik.yml`
  - `service/auth-service/opal.yml`
  - `service/platform-service/infrastructure/main.yml`
  - `service/search-service/README.md`
  - `service/user-service/README.md`
  - `ui/mobile/README.md`
- Binary artifacts in scope: 2
  - `infrastructure/infrastructure diagram.jpeg` (architecture diagram asset)
  - `service/user-service/gradle/wrapper/gradle-wrapper.jar` (standard Gradle wrapper JAR)

High-level inventory summary:

- one strong bootstrap toolchain: `service/platform-service/terraform`
- one strong intended control-plane shape: `infrastructure/`
- one concrete infra product stack: Kong
- one concrete registry stack: JFrog Artifactory
- one concrete application service: `user-service`
- one strong service-integration example set: Infisical subscriber examples
- many planned platform components named in docs and plans but not yet present on disk

## Bottom line

The canonical infrastructure pattern in `base-application` is not “use these exact manifests.” It is:

- bootstrap base cloud and cluster state with Terraform/OpenTofu-class tooling,
- use a small imperative bridge for first install,
- move quickly to Crossplane claims plus Flux reconciliation,
- keep platform-cluster concerns separate from application-cluster concerns,
- encode environment shape separately from app manifests,
- let individual services ship their own Kustomize-ready deployment bundle.

The repo proves that pattern best through its structure, not through a finished implementation. The older Terraform plus Ansible path is the closest thing to runnable infrastructure. The newer `infrastructure/` tree is the clearer statement of the desired long-term architecture. Any modern rebuild should preserve the layering and contracts, while discarding the broken path references, placeholder services, imperative side jobs, and outdated registry/object-storage assumptions.
