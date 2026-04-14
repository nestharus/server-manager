# Base-Application Infrastructure Pattern Index

Read against:

- `.refs/base-application/**` (full tree, including hidden files and embedded `.git`)
- `plans/proposals/phase1-foundation-v2.md`
- `plans/research/phase1-environments-and-benchmarks.md`
- `AGENTS.md`

This index focuses on the actual checked-in delivery pattern, not the aspirational story in the README.

## 1. Executive summary

`base-application` is not a single clean reference architecture. It is a layered but internally inconsistent platform sketch built around a `platform cluster + application clusters` model, with two overlapping control planes:

- An operator-run `Terraform/OpenTofu -> local-exec -> Ansible/Helm` bootstrap path in `service/platform-service/terraform/*` and `infrastructure/playbooks/*`
- An in-cluster `Flux -> Crossplane -> Kustomize/Helm` GitOps path in `infrastructure/platform-flux-system/*`, `infrastructure/flux-system/*`, and `infrastructure/crossplane/*`

The most reusable idea for Humility is the separation of concerns:

- bootstrap the base cluster first
- run a small in-cluster control plane after bootstrap
- keep service deployment manifests inside each service repo
- give each environment or cluster an explicit GitOps root

The most important caution is that the checked-in repo does not fully implement its own README. The README describes a multi-tenant platform with MinIO claim buckets, shared-vs-dedicated stacks, Infisical, Elasticsearch, OPAL/Cedar, Cloudflare, GitLab CI, Authentik, and a deployment tool. On disk, only a smaller skeleton is real:

- Crossplane provider/XRD/composition
- Flux Kustomizations and image automation
- Kong manifests
- JFrog Artifactory manifests
- `user-service` code plus service manifests
- `platform-service` Terraform/Ansible scaffolding
- a Dagger-based local container simulator

Everything else is either missing, empty, example-only, or contradicted by other files.

Against Humility's current Phase 1 direction, this repo is useful as evidence that the right shape is not a flat single-cluster draft. It does support a `bootstrap cluster -> per-cluster GitOps -> service-owned manifests` pattern. But it is far too enterprise-heavy and too internally inconsistent to copy literally.

## 2. Architecture layers

### Layer A: Repository and meta scaffolding

- `.refs/base-application/.git/*` is a full embedded clone of `git@github.com:nestharus/base-application.git`, not architecture.
- `.refs/base-application/.claude/agents/*` is a large library of generic "studio" agent prompts and does not describe runtime infrastructure.
- `.refs/base-application/.claude/tasks/infrastructure-implementation-plan.md` is an aspirational backlog, not evidence of deployed components.

### Layer B: Operator bootstrap from outside the cluster

There are two separate operator bootstrap paths:

- `service/platform-service/terraform/*`
  - creates a Vultr VPC and VKE cluster
  - writes kubeconfig locally
  - runs Ansible playbooks for Crossplane, Infisical, Flux, and MinIO
- `infrastructure/platform.tf`
  - creates a separate platform VPC and platform VKE cluster
  - writes kubeconfig locally
  - runs platform setup, Crossplane, and Flux playbooks

These two paths overlap instead of forming one coherent foundation.

### Layer C: In-cluster control plane

- `infrastructure/crossplane/providers/provider-vultr.yaml`
- `infrastructure/crossplane/xrds/kubernetes-cluster.yaml`
- `infrastructure/crossplane/compositions/kubernetes-cluster.yaml`
- `infrastructure/platform-flux-system/crossplane-resources.yaml`

This is the intended "platform cluster provisions clusters" layer.

### Layer D: GitOps reconciliation

- `infrastructure/platform-flux-system/*` is the platform-cluster Flux set
- `infrastructure/flux-system/*` is the application-cluster Flux set
- `infrastructure/clusters/*` provides cluster bootstrap templates, environment-type config, and example cluster claims
- service manifests are reconciled from repo subpaths, especially `service/user-service/src/main/resources/infrastructure/*`

### Layer E: Shared platform services

Real checked-in manifests exist for:

- JFrog Artifactory: `infrastructure/jfrog-artifactory/*`
- Kong: `infrastructure/kong/*`

Narrative-only or imperative-only components include:

- Infisical: no `infrastructure/infisical/` directory; only Ansible bootstrap in `service/platform-service/terraform/playbook/infisical.yml`
- MinIO: only Ansible bootstrap in `service/platform-service/terraform/playbook/minio.yml`
- Elasticsearch, monitoring, Cloudflare, OPAL/Cedar, GitLab CI, Authentik: described in docs, absent as infrastructure directories

### Layer F: Service delivery

The real service delivery pattern is "service repository owns its own deployment manifests":

- `service/user-service/src/main/resources/infrastructure/*`

Flux is supposed to point directly at that service subpath via:

- `infrastructure/flux-system/user-service-source.yaml`
- `infrastructure/flux-system/image-automation.yaml`

### Layer G: Local simulation

- `.dagger/src/pipeline/main.py`
- `infrastructure/playbooks/container-*.yml`

This creates a second, container-mode universe for local simulation rather than reusing the Kubernetes control plane directly.

## 3. Component inventory

| Component | Primary files | What is actually present | Assessment |
| --- | --- | --- | --- |
| Root README | `README.md` | Two short notes about env vars, Flagsmith, Infisical, and Flux watching S3 claim JSON | Directional note, not architecture |
| Infrastructure README | `infrastructure/README.md` | 895-line architecture narrative | Mostly aspirational; larger than what the tree implements |
| Platform Terraform | `infrastructure/platform.tf` | VPC, platform VKE, VPC peering, local kubeconfig, local-exec Ansible | Partial and internally incomplete |
| Platform-service Terraform | `service/platform-service/terraform/*` | Generic Vultr VPC/VKE modules plus Ansible chaining | Most concrete bootstrap path in repo |
| Crossplane | `infrastructure/crossplane/*` | Provider, one XRD, one composition | Real skeleton, not full implementation |
| Platform Flux | `infrastructure/platform-flux-system/*` | Flux Kustomizations for platform sync and Crossplane resources | Real skeleton with broken references |
| App Flux | `infrastructure/flux-system/*` | Infrastructure sync, app cluster sync, user-service sync, image automation | Real skeleton with broken references |
| Cluster templates | `infrastructure/clusters/*` | Environment type ConfigMaps, example cluster claims, bootstrap manifests | Real files, weakly wired |
| Kong | `infrastructure/kong/*` | HelmRelease, KongIngress/Ingress/Plugin resources, post-install job | Real manifest set for one shared Kong shape |
| JFrog Artifactory | `infrastructure/jfrog-artifactory/*` | HelmRelease, registry secrets, namespace | Real manifest set with placeholder creds |
| Infisical | `service/platform-service/terraform/playbook/infisical.yml` | Imperative Helm/API bootstrap only | No declarative infra dir; not GitOps-native |
| MinIO | `service/platform-service/terraform/playbook/minio.yml` | Imperative Helm/API/bootstrap only | No checked-in GitOps directory; very imperative |
| User service | `service/user-service/**` | Java scaffold, Gel schema, Kubernetes manifests | Only substantive service, but not runnable as-is |
| Other services | `service/ai-service`, `auth-service`, `invoice-service`, `message-service`, `search-service` | README bullets or empty files | Mostly placeholders |
| Platform service app | `service/platform-service` | Terraform, examples, notes, version | No actual app source tree |
| Dagger local mode | `.dagger/*` | Container simulation of platform + env services | Real, but divergent from README and cluster path |
| `.claude` task plan | `.claude/tasks/infrastructure-implementation-plan.md` | 1,856-line backlog with 249 unchecked tasks | Useful as ambition signal, not shipped state |

## 4. Crossplane pattern

### Intended pattern

The intended Crossplane model is:

1. A pre-existing platform cluster installs Crossplane.
2. Crossplane exposes a `KubernetesCluster` claim.
3. Flux applies cluster claims.
4. Crossplane provisions VPCs and Kubernetes clusters for environments.
5. Flux then bootstraps those clusters.

Primary files:

- `infrastructure/crossplane/providers/provider-vultr.yaml`
- `infrastructure/crossplane/xrds/kubernetes-cluster.yaml`
- `infrastructure/crossplane/compositions/kubernetes-cluster.yaml`
- `infrastructure/platform-flux-system/platform-cluster.yaml`
- `infrastructure/clusters/cluster-template.yaml`
- `infrastructure/clusters/environments/dev-team1.yaml`
- `infrastructure/clusters/environments/prod-main.yaml`

### What the XRD models

`infrastructure/crossplane/xrds/kubernetes-cluster.yaml` models:

- `clusterType`: `platform` or `application`
- `environmentName`
- `environmentType`: `dev`, `staging`, `prod`, `sue`
- `enableHA`
- `nodePools[]`
- status fields for cluster endpoint, cluster ID, and VPC ID

This is the main abstraction seam in the repo.

### What the composition actually provisions

`infrastructure/crossplane/compositions/kubernetes-cluster.yaml` currently creates only:

- one Vultr `VPC`
- one Vultr `Kubernetes` cluster
- one `NodePool` for `general-restricted`
- one `NodePool` for `general-public`
- one Kubernetes `Secret` object intended to hold kubeconfig

### Important gaps and contradictions

- The composition ignores `spec.parameters.nodePools` entirely. Environment types define many pools (`memory`, `storage`, `spot`, `ai`), but the composition only creates two fixed pools.
- The composition does not patch labels or taints from the XRD `nodePools` schema into the actual Vultr node pools.
- The composition barely uses `environmentType`; it does not turn `dev`, `staging`, `prod`, or `sue` into distinct provisioning behavior.
- The kubeconfig `Secret` object uses `providerConfigRef.name: kubernetes-provider`, but there is no `ProviderConfig` named `kubernetes-provider` anywhere under `infrastructure/`.
- The kubeconfig `Secret` object patches only metadata name/namespace. It does not patch kubeconfig data from the created cluster, so the generated secret would be empty even if the provider existed.
- `platform-flux-system/platform-cluster.yaml` declares the platform cluster itself as a `KubernetesCluster` claim, but Flux must already be running in a platform cluster for that file to matter. That makes it circular as a bootstrap path.
- `infrastructure/platform.tf` separately provisions a platform cluster outside Crossplane anyway, so the repo contains two conflicting answers to "who creates the platform cluster?"

### Crossplane pattern verdict

Reusable for Humility:

- the idea of a single claim type for cluster requests
- the split between external bootstrap and in-cluster steady-state reconciliation

Too heavy or too incomplete for Humility:

- Crossplane-managed cluster-of-clusters in Phase 1
- environment-type-driven node-pool abstraction when the composition does not actually honor it
- self-hosting the platform cluster as a claim inside itself

## 5. Flux pattern

### Real checked-in Flux shape

Platform-cluster Flux files:

- `infrastructure/platform-flux-system/kustomization.yaml`
- `infrastructure/platform-flux-system/platform-sync.yaml`
- `infrastructure/platform-flux-system/crossplane-resources.yaml`
- `infrastructure/platform-flux-system/platform-cluster.yaml`

Application-cluster Flux files:

- `infrastructure/flux-system/kustomization.yaml`
- `infrastructure/flux-system/infrastructure-sync.yaml`
- `infrastructure/flux-system/application-clusters.yaml`
- `infrastructure/flux-system/user-service-source.yaml`
- `infrastructure/flux-system/image-automation.yaml`

Bootstrap files for new clusters:

- `infrastructure/clusters/bootstrap/flux-system.yaml`
- `infrastructure/clusters/bootstrap/kustomization.yaml`

### Actual pattern

Flux is used for three different jobs:

- sync the repo's infrastructure directories
- sync Crossplane provider/XRD/composition resources
- sync service-owned deployment manifests

Kustomize is the assembly layer for all of the above, and Helm is used underneath Flux for JFrog and Kong.

### Real strengths

- GitRepository/Kustomization objects are split by concern rather than jammed into one manifest.
- Service deployment manifests live with the service code and are pulled by Flux from that subpath.
- Image automation is meant to update the service manifest path directly rather than update a central environment file.

### Concrete defects

- `infrastructure/flux-system/kustomization.yaml` references `node-pools-sync.yaml`, but that file does not exist.
- `infrastructure/platform-flux-system/platform-sync.yaml` syncs `./infrastructure/infisical`, but `infrastructure/infisical/` does not exist.
- `infrastructure/clusters/bootstrap/flux-system.yaml` points at `ssh://git@github.com/your-org/your-repo`, a placeholder, not a real source.
- The same bootstrap file syncs `path: ./infrastructure`, which collapses back to a flat environment-agnostic root. That directly conflicts with the Humility Phase 1 v2 direction of explicit per-cluster GitOps roots.
- `infrastructure/flux-system/application-clusters.yaml` health-checks `dev-cluster`, `staging-cluster`, `prod-cluster`, and `sue-cluster`, but the checked-in example claims are `dev-team1-cluster` and `prod-main-cluster`.
- `infrastructure/flux-system/user-service-source.yaml` depends on a Flux Kustomization named `crossplane-system`, but no such Kustomization exists under the repo's Flux manifests.

### Flux pattern verdict

Reusable for Humility:

- one bootstrap step, then GitOps for steady state
- separate GitRepository/Kustomization objects per concern
- service-owned manifests plus optional image automation

Needs simplification or replacement:

- any pattern where Flux is expected to "watch S3" or MinIO claim buckets
- any pattern that syncs one flat root instead of a cluster-specific root
- image automation before the registry and deployment path are actually stable

## 6. Environment model

### Intended model

The repo clearly wants a two-level environment model:

- a `platform` cluster for shared services
- many `application` clusters

Within application clusters it defines four environment types:

- `dev`
- `staging`
- `prod`
- `sue`

Evidence:

- `infrastructure/crossplane/xrds/kubernetes-cluster.yaml`
- `infrastructure/clusters/environment-types/*.yaml`
- `infrastructure/README.md`

### How environment types are modeled

`infrastructure/clusters/environment-types/*.yaml` stores each type as a `ConfigMap` with:

- `cluster.enableHA`
- `cluster.nodePools[]`
- feature flags such as `monitoring`, `backup`, and `costOptimization`

Example claims then bind an `environmentName` and `environmentType`:

- `infrastructure/clusters/environments/dev-team1.yaml`
- `infrastructure/clusters/environments/prod-main.yaml`

`infrastructure/clusters/cluster-template.yaml` says `enableHA` and `nodePools` "will be populated from environment type ConfigMap".

### What is real versus effective

The environment-type ConfigMaps are real files, but they are mostly descriptive, not operative:

- nothing in the Crossplane composition parses the ConfigMap payload
- nothing turns `config.yaml` into `spec.parameters.nodePools`
- nothing applies the environment-type feature flags

So the environment model is best described as:

- conceptually strong
- partially encoded
- not actually enforced by the checked-in composition

### Inconsistencies

- `README.md` mentions `sue` and a Flux/S3 claim flow, but only as a note.
- `infrastructure/README.md` uses both `stage` and `staging`, and both `prod` and `production`.
- Humility's current Phase 1 docs use `dev`, `staging`, `production`; base-application adds `sue`, which looks like an enterprise experimentation tier rather than a near-term need.

### Environment model verdict

Reusable for Humility:

- explicit environment typing
- clear separation between a long-lived platform substrate and per-environment workloads
- named example environments like `dev-team1` or `prod-main`

Too heavy or out of scope:

- a dedicated `sue` lifecycle for experimentation
- shared-vs-dedicated stateful service topologies per environment type in Phase 1
- MinIO-backed claim files as the environment source of truth

## 7. Service patterns

### Service-owned deployment manifests

The strongest service pattern in the repo is that service infrastructure lives inside the service repository itself:

- `service/user-service/src/main/resources/infrastructure/namespace.yaml`
- `service/user-service/src/main/resources/infrastructure/deployment.yaml`
- `service/user-service/src/main/resources/infrastructure/service.yaml`
- `service/user-service/src/main/resources/infrastructure/hpa.yaml`
- `service/user-service/src/main/resources/infrastructure/network-policy.yaml`
- `service/user-service/src/main/resources/infrastructure/kustomization.yaml`

Flux is supposed to deploy these directly from repo source.

### Runtime assumptions inside service manifests

The manifests assume:

- images come from JFrog at `jcr.example.com`
- workloads run on `general-public` nodes
- image pull secrets are pre-distributed
- HPA is available
- Kong routes traffic to services

### `user-service` reality check

`user-service` is the only substantive service scaffold, but it is not deployable as written:

- `src/main/java/Server.java` creates Dagger and Vertx but never starts an HTTP server.
- `src/main/java/service/UserService.java` contains only commented example code.
- the deployment probes `/health/live` and `/health/ready`, but nothing in the code serves those endpoints.
- the code expects `GEL_*` variables in `module/GelConnectionModule.java` and `module/GelClientConfigModule.java`.
- the deployment injects `DATABASE_URL`, `DATABASE_USERNAME`, and `DATABASE_PASSWORD` instead.

That means the service manifests are ahead of the application implementation.

### Platform-service pattern

`platform-service` is not an implemented service. It is an infrastructure orchestrator bundle:

- `service/platform-service/terraform/*`
- `service/platform-service/terraform/playbook/*`
- `service/platform-service/example/*`

There is no actual `src/` tree for a platform API, no environment lifecycle server, and no MinIO bucket watcher.

### Secret integration pattern

The intended secret pattern is:

- Kubernetes native auth against Infisical
- service-owned webhook subscribers for secret rotation
- no long-lived service tokens

Evidence:

- `service/platform-service/example/secret/README.md`
- `service/platform-service/example/secret/python_subscriber.py`
- `service/platform-service/example/secret/JavaSecretSubscriber.java`

But the imperative MinIO playbook contradicts that by creating and storing a service token via `INFISICAL_MACHINE_TOKEN`, and it even switches paths between `/platform/minio` and `/minio`:

- `service/platform-service/terraform/playbook/minio.yml`

### Service pattern verdict

Reusable for Humility:

- service-owned deployment manifests
- keeping infra next to service code
- simple Kustomize packaging per service

Not reusable as-is:

- placeholder registry assumptions
- HPA-and-Kong-before-service code exists
- secret patterns that mix "no long-lived tokens" with machine-token bootstrap

## 8. What’s complete vs stub

### Real checked-in assets

- Crossplane provider, XRD, and composition skeleton
- Flux GitRepository/Kustomization/image automation skeleton
- Kong HelmRelease plus route/plugin/config-job manifests
- JFrog Artifactory HelmRelease plus registry secret distribution
- `platform-service` Terraform and Ansible bootstrap scaffolding
- Dagger local container simulator
- `user-service` build, schema, and Kubernetes manifests

### Present on disk but effectively stubbed or broken

- `infrastructure/platform.tf`
  - references `var.vultr_region`, `var.cluster_name`, `var.kubernetes_version`, and `vultr_vpc.kubernetes`, none of which are defined in that directory
- `infrastructure/crossplane/compositions/kubernetes-cluster.yaml`
  - defines an empty kubeconfig `Secret`
  - references missing `kubernetes-provider`
- `infrastructure/flux-system/kustomization.yaml`
  - references missing `node-pools-sync.yaml`
- `infrastructure/platform-flux-system/platform-sync.yaml`
  - points to missing `infrastructure/infisical/`
- `service/user-service/*`
  - deployment contract does not match code contract
- `infrastructure/clusters/*`
  - environment-type ConfigMaps exist but are not actually consumed

### Narrative-only or missing

- `infrastructure/infisical/`
- `infrastructure/elasticsearch/`
- `infrastructure/monitoring/`
- `infrastructure/cloudflare/`
- `infrastructure/opal-cedar/`
- `infrastructure/gitlab-ci/`
- `infrastructure/authentik/`
- any real `platform-deployment-tool` package
- any platform API implementation
- any MinIO claim watcher
- any static-environment GitOps repository integration

### Empty placeholder files

Seven checked-in files are empty:

- `service/README.md`
- `service/search-service/README.md`
- `service/auth-service/opal.yml`
- `service/auth-service/authentik.yml`
- `service/user-service/README.md`
- `service/platform-service/infrastructure/main.yml`
- `ui/mobile/README.md`

### Biggest signal

The repo is a partially materialized blueprint, not a shipping platform. The checked-in code is enough to extract patterns, but not enough to treat the README as source-of-truth.

## 9. What needs modernization

### Reusable for Humility

- Keep a clean split between external bootstrap and in-cluster reconciliation.
- Keep service deployment manifests in the service repo.
- Keep explicit environment names and typed environment classes.
- Keep per-cluster or per-environment GitOps roots.
- Keep small, declarative Flux/Kustomize units rather than giant bootstrap bundles.

### Dagger-era assumptions to simplify

- The Dagger pipeline in `.dagger/src/pipeline/main.py` models the platform as `docker:24-dind` containers, not real clusters.
- `infrastructure/README.md` documents commands like `create_local_platform` and `deploy_environment`, but the actual Dagger file only exposes `main_pipeline`.
- The Dagger JFrog path still references `docker.bintray.io/jfrog/artifactory-jcr`, which is a legacy-era assumption.
- For Humility, a second container-mode universe is probably unnecessary. A real preview/dev cluster plus normal local dev is simpler and less misleading.

### JFrog / Artifactory assumptions to simplify

- The repo assumes a self-hosted JFrog Artifactory with Docker and OCI repositories, user-local repos, and retention logic.
- Real manifests hardcode placeholder registry credentials and bootstrap behavior with `changeme` and `admin:password`.
- For Humility, this is likely far too enterprise-heavy. A simpler OCI/container registry is enough.

### S3-style artifact and claim compromises to simplify

- The README treats MinIO/S3 as a deployment claim bus and hints that Flux should react to bucket contents.
- Flux does not natively "watch S3 buckets" in the way the root `README.md` note implies.
- The repo also splits environments into dynamic MinIO-managed claims versus Git-managed claims, creating dual control planes.
- For Humility, Git should remain the source of truth for environment and deployment state. Object storage should be reserved for backups, benchmark results, or large artifacts, not as the main mutation surface.

### Security and secret model to simplify

- Infisical bootstrap is extremely imperative: Helm deploy, local port-forward, REST API bootstrap, local credential dump to `/tmp`, custom auth manager deployment.
- MinIO secret flow contradicts its own "no long-lived tokens" story by using `INFISICAL_MACHINE_TOKEN`.
- For Humility, prefer one declarative secret path and one auth model.

### Stateful platform sprawl to avoid in Phase 1

The base-application README assumes all of these eventually live inside the platform:

- JFrog
- Infisical
- MinIO
- Elasticsearch
- Grafana/Prometheus
- Kong
- OPAL/Cedar
- Authentik
- GitLab runners
- Cloudflare automation

That is far beyond Humility's current foundation scope. The current Humility Phase 1 proposal is right to stay narrower.

### Specific things that are too enterprise-heavy or out of scope

- shared-vs-dedicated Elasticsearch, monitoring, Kong, and auth stacks by environment type
- self-hosted JFrog plus OCI-artifact packaging conventions
- Crossplane-managed ephemeral cluster fleet for app environments
- MinIO claim buckets as environment control plane
- `sue` environments as a first-class platform tier
- Cloudflare WAF automation and GitLab CI runner estate in the base layer

## 10. Dependency graph

### Main bootstrap path actually present

```text
Operator workstation
  -> Terraform/OpenTofu
     -> Vultr VPC + VKE cluster(s)
     -> local kubeconfig file(s)
     -> local-exec Ansible
        -> base cluster setup
        -> Crossplane install
        -> Flux install
        -> Infisical install (imperative path)
        -> MinIO install (imperative path)
        -> platform security/storage primitives
  -> Flux on platform cluster
     -> Crossplane provider/XRD/composition
     -> platform services sync
     -> cluster claim manifests
  -> Crossplane
     -> intended provisioning of application clusters
  -> Flux bootstrap on application clusters
     -> sync repo infrastructure path
     -> sync service manifests
     -> deploy Kong and service workloads
```

### Service delivery path

```text
Service repo path
  -> service-owned Kustomize package
  -> Flux GitRepository + Kustomization
  -> image automation updates manifest image tag
  -> pods pull from Artifactory-style registry
  -> traffic enters through Kong
```

### Local simulation path

```text
Developer
  -> Dagger pipeline
     -> docker-in-docker "platform" container
     -> docker-in-docker "environment" container
     -> container-mode Ansible playbooks
     -> simulated Infisical/JFrog/Kong
```

### Critical dependency mismatches

- Crossplane claims depend on Flux being alive in the platform cluster, so they are not the first bootstrap step.
- Application cluster bootstrap depends on kubeconfig secrets that the current composition does not actually populate.
- Platform Flux depends on directories that are missing from the repo.
- Service delivery depends on registry creds and health endpoints that are placeholders or absent.

## 11. Raw statistics

- Total files under `.refs/base-application/`: `192`
- Files tracked by embedded Git `HEAD`: `164`
- Text lines excluding `.git/*`: `17,305`
- Top-level file counts:
  - `service`: `67`
  - `infrastructure`: `47`
  - `.claude`: `40`
  - `.git`: `28`
  - `.dagger`: `6`
- File type counts:
  - `.md`: `55`
  - `.yaml`: `40`
  - `.yml`: `16`
  - files with no extension: `17`
  - `.java`: `11`
  - `.gradle`: `8`
  - `.py`: `5`
  - `.tf`: `5`
  - `.tfvars`: `3`
  - `.gel`: `2`
  - `.jpeg`: `1`
  - `.jar`: `1`
- Actual top-level infrastructure directories on disk: `7`
  - `clusters`
  - `crossplane`
  - `flux-system`
  - `jfrog-artifactory`
  - `kong`
  - `platform-flux-system`
  - `playbooks`
- README-promised infrastructure entries missing as directories:
  - `elasticsearch`
  - `monitoring`
  - `cloudflare`
  - `infisical`
  - `opal-cedar`
  - `gitlab-ci`
  - `authentik`
  - `node-pools/` is promised as a directory, but only `node-pools.yaml` exists, and it is explicitly marked `DEPRECATED`
- Infrastructure YAML `kind:` declarations: `60`
- `user-service` infrastructure YAML `kind:` declarations: `8`
- Empty files: `7`
- `.claude/tasks/infrastructure-implementation-plan.md`:
  - total lines: `1,856`
  - unchecked tasks: `249`
  - `QUESTION FOR USER` markers: `96`
  - `to be created` markers: `8`
- Concrete placeholder markers found in live manifests or bootstrap files:
  - `jcr.example.com`
  - `fluxcdbot@example.com`
  - `ssh://git@github.com/your-org/your-repo`
  - `changeme`
  - `admin:password`
- Missing referenced file:
  - `infrastructure/flux-system/node-pools-sync.yaml`
- Missing referenced provider:
  - `kubernetes-provider` in `infrastructure/crossplane/compositions/kubernetes-cluster.yaml`

## Bottom line

`base-application` is a useful reference for delivery shape, not for literal implementation. The real pattern it demonstrates is:

- bootstrap a base cluster externally
- install a small in-cluster control plane after bootstrap
- let Flux reconcile small Kustomize units
- keep service deployment manifests with the service

That part aligns with Humility's move away from the earlier flat single-cluster draft.

The rest should be treated skeptically. The checked-in repo does not support the full enterprise story told by `infrastructure/README.md`. For Humility, the right takeaway is to borrow the layering and per-cluster GitOps idea, then simplify aggressively:

- use explicit per-cluster GitOps roots
- keep Git as the source of truth
- avoid S3 claim buses
- avoid self-hosting JFrog, Elasticsearch, OPAL/Cedar, Authentik, and Cloudflare automation in Phase 1
- avoid a Dagger/container shadow platform unless there is a concrete need for it

If later Humility proposals cite `base-application`, they should cite it as a reference for separation of concerns and control-plane layering, not as proof that the repo already contains a coherent, working, production-ready platform stack.
