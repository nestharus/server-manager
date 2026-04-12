# Unified Platform Index

This file merges the four legacy platform decomposition indexes, applies the user-specified modernizations, resolves the major architectural overlaps, and orders the work around the immediate `server-manager` bot need.

## 1. Executive summary

The unified platform is no longer a Railway/Supabase-style hosted stack and no longer a Dagger-centric custom CI substrate. After modernization, the target is a self-managed Kubernetes platform running on a low-cost VPS provider (`Vultr` or `Hetzner`), provisioned with **OpenTofu**, reconciled with **Flux CD**, built and deployed through **Buildkite**, and backed by **PostgreSQL** plus an S3-compatible object store. The platform keeps the legacy documents' strongest common ideas: Git-reviewed desired state, Kubernetes as the runtime substrate, PostgreSQL as the system of record, Authentik-centered identity, Pomerium + step-ca for operator access, Infisical for secrets, Kong at public ingress, and a metrics/logs/traces stack rich enough to support correlated debugging.

The major subsystems are:

- Foundation: provider selection, VPS/Kubernetes bootstrap, OpenTofu, Flux CD, Git repos, ingress, object storage.
- Data plane: PostgreSQL, Debezium, Kafka, registry, and environment state schemas.
- Security and access: Authentik, Kong, Pomerium, step-ca, Infisical, break-glass governance, and an unresolved fine-grained authorization slot (`OPAL/Cedar` vs `Casbin` research).
- Observability and operations: Prometheus-compatible metrics, VictoriaMetrics/vmagent/vmalert, Elastic logs/traces, OpenTelemetry, optional StackStorm automation, and later hardening layers such as Cloudflare, Trivy, Falco, Calico, Velero, and OpenCost.
- Applications: the immediate `server-manager` Discord bot, then any future admin UI, web API, or pilot workload.

The core merge decision is to treat **Buildkite + OpenTofu + Flux CD** as the new control-plane spine. That collapses or downgrades a large amount of legacy custom platform machinery: Dagger-specific caches, GitLab-runner assumptions, the bucket-watched Flux pattern, much of the custom build-orchestrator surface, and Terraform-controller-specific auth rollout logic. The remaining major unresolved choices are provider (`Vultr` vs `Hetzner`), fine-grained authorization (`OPAL/Cedar` vs `Casbin`), and how much of Crossplane/custom deployment orchestration survives once Buildkite and OpenTofu are in place.

`DECISIONS.md` still locks the current Discord bot MVP to Railway + Supabase. This document should therefore be read as the merged future-state platform index, not as an already-approved migration plan for the live bot project.

## 2. Unified component inventory

Source doc abbreviations:

- `A` = `auth-v5-index.md`
- `E` = `expansion-plan-index.md`
- `G` = `gitops-index.md`
- `P` = `platform-v2-index.md`
- `modernization` = introduced by the user's non-negotiable replacements
- `project` = this repo's current Discord-bot context

Grouped rows intentionally normalize aliases and appendix-only bundles. The notes column calls out the exact legacy bundles that are being collapsed.

| Component | Source doc(s) | Role | Category | Status | Notes |
|---|---|---|---|---|---|
| Buildkite | A,E,G,P | Canonical CI engine and job runner | CI/CD | NEW | Fulfills legacy `CI pipeline`, GitLab-runner, and Dagger orchestration roles. |
| OpenTofu | A,E,P, modernization | Canonical IaC engine | CI/CD | NEW | Replaces Terraform-as-branded-tool and manual dashboard workflows. |
| Vultr | E,P | VPS/provider candidate | foundation | EVALUATE | Still viable, but no longer assumed via VKE. |
| Hetzner | modernization | Alternative VPS/provider candidate | foundation | NEW | Added by user modernization; must be researched against Vultr. |
| Kubernetes | A,E,P | Runtime/workload substrate | foundation | KEEP | Core orchestration layer survives all four documents. |
| VKE / managed Kubernetes | A,E,P | Legacy provider-managed cluster substrate | foundation | MODERNIZE | Replace VKE-specific assumptions with self-managed K8s on VPS. |
| S3-compatible object storage | E,P | Artifacts, backups, and claim storage | storage | MODERNIZE | Covers `Vultr Object Storage`; keep the role, not the vendor lock-in. |
| Git repos and review flow | A,G,P | Desired-state source + PR gate | CI/CD | KEEP | Covers GitOps monorepo, static env repo, generic Git, webhooks, PR review, and JSON env files. |
| Flux CD | A,E,P | Canonical GitOps reconciler | CI/CD | KEEP | User-modernized winner over Argo and over custom GitOps drift. |
| Flux terraform-controller path | A | In-cluster Terraform/OpenTofu apply model | CI/CD | DROP | Superseded by OpenTofu in CI unless a narrow exception survives. |
| Flux Kustomization | A | Dependency ordering and workload sync | CI/CD | KEEP | Still useful even without terraform-controller. |
| Terraform | A,E,P | Legacy IaC tool name | CI/CD | MODERNIZE | Replace with OpenTofu. |
| Crossplane stack | A,E,P | Declarative infra abstraction layer | foundation | EVALUATE | Covers Crossplane, Composition, provider-vultr, VKECluster, and cloud-init coupling. |
| Ansible + bastion bootstrap | A,E,P | Imperative bootstrap path | foundation | DROP | Conflicts with ZTNA goals and duplicates OpenTofu/bootstrap work. |
| Helm | P | Package/bootstrap installer | CI/CD | KEEP | Lightweight install tool still useful for cluster add-ons. |
| GitLab / Jenkins CI stack | E,P | Legacy CI substrates/comparators | CI/CD | DROP | Superseded by Buildkite + generic Git hosting. |
| Dagger and cache model | G,P | Legacy pipeline engine and cache contract | CI/CD | MODERNIZE | Build logic may survive; Dagger, shared VFS, and exact cache semantics do not. |
| Harbor and OCI artifacts | A,P | Artifact registry and image/bundle formats | storage | KEEP | Good fit for Kubernetes delivery regardless of CI engine. |
| Local dev harness | P | High-fidelity local simulation | dev | EVALUATE | Covers Kind, MinIO, and `kubectl`; useful later, not phase-1 critical. |
| PostgreSQL | E,G,P | System of record | data | KEEP | Deployment model changes, database choice does not. |
| `pg_stat_statements` | P | Query-level DB observability | observability | KEEP | Cheap, high-signal Postgres instrumentation. |
| Debezium | G,P | CDC from Postgres to event bus | data | KEEP | Keep for environment/event flows unless later simplification removes Kafka. |
| Kafka | A,G,P | Central event bus | data | KEEP | Full-platform event backbone; not on the bot's minimum path. |
| Redis | G | Ephemeral deployment counter store | data | DROP | Custom build aggregation should not require a separate cache at baseline. |
| Custom build state model | G | Build tables/topics for custom CI orchestration | data | EVALUATE | Covers `deployments`, `builds`, `platform.builds.v1`, and `platform.deployments.v1`; Buildkite may remove most of this. |
| Environment state model | G | Desired-state store for environments | data | KEEP | Covers `environments` table and `platform.environments.cdc.v1`. |
| Authentik | A,P | Sole IdP / identity source | auth | KEEP | Explicit user-confirmed keeper. |
| OIDC / MFA / JWT federation | A,P | Human login and token envelope | auth | KEEP | Covers OIDC, MFA, and JWT terms across the legacy docs. |
| Pomerium | A,P | ZTNA proxy and admin-access control plane | auth | KEEP | Includes `Pomerium API` for policy automation. |
| Kong | A,E,P | Public ingress/API gateway | networking | KEEP | Covers `Kong API Gateway` and expansion's Kong appendix bundle. |
| OPAL / Cedar | A,P | Fine-grained authorization plane | auth | EVALUATE | Must be compared directly with Casbin before implementation. |
| Application auth contract | A | App-side enforcement protocol | auth | EVALUATE | Covers ABAC, PEP, Cedar agent, Cedar query format, and HTTP query contract. |
| step-ca and SSH trust chain | A,P | JIT SSH certificate authority and verifier path | auth | KEEP | Covers step-ca, SSH, SSH certs, and `sshd`. |
| JIT access client chain | A | End-user operator workflow | auth | KEEP | Covers SSH agent, ProxyCommand, wrapper script, `pomerium-cli`, `step-cli`, browser flow, RDP, and TCP-over-HTTPS tunneling. |
| Infisical | A,E,P | Canonical secret authority | security | KEEP | Expansion appendix only adds adjacent research; the chosen system stays Infisical. |
| Infisical sync path | A,P | Secret delivery into Kubernetes | security | KEEP | Covers InfisicalSecret, Infisical Operator, and mounted Kubernetes Secrets. |
| Infisical direct runtime API access | A | Direct runtime secret fetch path | security | DROP | Explicitly forbidden by the auth spec. |
| KMS / PKI adjuncts | E | Advanced key-management options | security | EVALUATE | Covers PKI, `k8-kms-plugin`, AWS KMS, Kubernetes KMS provider, and KMIP research. |
| External Secrets Operator | E | Alternate secret sync mechanism | security | DROP | Superseded by the InfisicalSecret path. |
| Cloudflare edge | E | DNS, WAF, DDoS, and origin lockdown | networking | KEEP | Expansion's selected edge layer. |
| Ingress controller | A | Base in-cluster ingress dependency | networking | KEEP | Needed before Kong/Pomerium policy rollouts. |
| Gateway API | E | Ingress/control-surface alternative | networking | EVALUATE | Keep as a standards-track option around Kong, not as the chosen gateway. |
| HAProxy Ingress | E | Ingress alternative | networking | DROP | No legacy document actually chooses it. |
| Linkerd | P | Service mesh | networking | EVALUATE | Valuable, but not required for the first bot-delivery slice. |
| Calico / NetworkPolicy | E | Default-deny pod networking | networking | KEEP | Covers Calico plus the CNI/NetworkPolicy bundle. |
| Trivy stack | E | Supply-chain scanning | security | KEEP | Covers CI scan gate plus in-cluster Trivy Operator. |
| Falco | E | Runtime threat detection | security | KEEP | Later-phase hardening layer. |
| Velero stack | E | Backup and restore | storage | KEEP | Covers Velero, Restic, and VolumeSnapshots. |
| OpenCost | E | Cost visibility | observability | KEEP | Later-phase FinOps slice. |
| FinOps comparators | E | Alternative cost-tool corpus | observability | DROP | Covers Kubecost, CloudZero, and Apptio research only. |
| Prometheus-compatible metrics stack | A,E,P | Metrics collection, storage, and alert production | observability | KEEP | Covers Prometheus, exposition format, exporters, vmagent, vmalert, and VictoriaMetrics. |
| Elastic stack | A,E,G,P | Logs, traces, enrichment, anomaly source | observability | KEEP | Covers Elasticsearch, Kibana, Elastic APM, ingest pipeline, and anomaly detection. |
| Grafana | A,E,P | Metrics dashboards and admin UI | observability | KEEP | Separate operational surface from the metrics backend itself. |
| OpenTelemetry + OTLP | E,P | Telemetry instrumentation and context propagation | observability | KEEP | Durable standard across logs, metrics, and traces. |
| StackStorm | A,P | Alert-driven automation | ops | EVALUATE | Useful, but optional until ops burden justifies it. |
| Observability component placeholder | E | Legacy unnamed observability box | observability | DROP | Replaced by explicit metrics/logs/traces components. |
| Traffic management placeholder | E | Legacy unnamed ingress box | networking | DROP | Replaced by Kong + ingress + Cloudflare. |
| FastAPI / Python / Pydantic | G,P | Platform API implementation stack | app | KEEP | Good fit for the current Python-heavy codebase and existing contracts. |
| Platform Service | G,P | Environment control-plane API | app | KEEP | Covers `environment-manager-api service` plus `Platform Service`. |
| Platform Deployer | P | Desired-state-to-claim renderer | app | EVALUATE | Only needed if the dynamic-environment pipeline survives as designed. |
| Custom orchestration services | G | Legacy custom builder/orchestrator/timeouts | app | CONFLICT | Covers Orchestrator, Builder Services, Timeout-management Service; Buildkite may absorb most of this. |
| GitOps Controller | G | Git-to-database reconciler | app | CONFLICT | Directly overlaps with Flux as the canonical reconciler. |
| Custom Frontend | G | Custom build/debug UI | app | DROP | Start with Buildkite UI + Kibana/Grafana, not a new frontend. |
| Legacy perimeter access | A | Old trust model to retire | security | DROP | Covers VPC trust, VPNs, bastions, and static SSH keys. |
| Break-glass surface | A | Emergency access and audit path | security | MODERNIZE | Keep the process; make the portal/audit path provider-agnostic rather than Vultr-specific. |
| KEDA / HPA | P | Workload autoscaling | compute | KEEP | Coherent later-phase scaling layer. |
| Karpenter | P | Node autoscaling | compute | EVALUATE | Provider support on Vultr/Hetzner needs fresh research. |
| Flink Adaptive Scheduler | P | Stateful job autoscaling | compute | DROP | No current workload evidence justifies carrying this forward. |
| Cloud comparators | E | External architecture corpus | foundation | DROP | Covers EKS, GKE, Rancher, and etcd reference material only. |
| `server-manager` | project | Immediate workload to host | application | NEW | Not in the legacy docs, but it is the reason this platform needs to exist. |

## 3. Conflict register

| Conflict ID | What | Documents involved | Resolution |
|---|---|---|---|
| C1 | CI engine disagreement: Dagger-centered custom CI, GitLab-runner execution, and generic unspecified CI are all present. | E, G, P | **Buildkite wins.** Keep Git/PR workflow and artifact promotion, but replace Dagger/GitLab/Jenkins as the canonical CI engine. |
| C2 | IaC tooling is split between Terraform, controller-driven Terraform, and manual/cloud-dashboard habits carried from adjacent work. | A, E, P | **OpenTofu wins.** Treat Terraform as a renamed legacy tool choice and remove dashboard-managed infra from the target architecture. |
| C3 | GitOps reconciliation is split between Flux CD and a custom GitOps Controller that writes Git state into PostgreSQL. | A, G, P | **Flux CD wins for canonical reconciliation.** Keep a custom controller only if dynamic environments truly need a Git-to-DB bridge after research. |
| C4 | Desired-state source is inconsistent: Git repo, object-storage bucket, and database-backed controller flows all claim to be authoritative. | G, P | **Git repo is authoritative for static desired state.** Database-backed desired state remains only for API-driven dynamic environments; object storage is not the primary GitOps source. |
| C5 | Hosting substrate is Vultr/VKE-specific in the legacy docs, but the user requires low-cost VPS hosting on Vultr or Hetzner. | A, E, P | **Provider-managed VKE loses.** Replace VKE assumptions with self-managed Kubernetes on VPS; final provider stays open between Vultr and Hetzner. |
| C6 | Fine-grained authorization is specified as OPAL/Cedar in legacy docs, but the current modernization request explicitly reopens the choice against Casbin. | A, P | **No winner yet.** Keep Authentik, Kong, Pomerium, and step-ca; run a dedicated research pass for `OPAL/Cedar` vs `Casbin` before implementing app auth. |
| C7 | Infra control-plane ownership overlaps: Crossplane, terraform-controller, and OpenTofu can all end up managing the same surfaces. | A, E, P | **OpenTofu + Flux form the baseline.** Crossplane stays in the design only if research proves it is the cleanest way to support dynamic environment claims. |
| C8 | Bastion/Ansible bootstrap conflicts with the zero-trust/JIT-access principles in the auth design. | A, P | **Zero-trust wins.** Treat bastion-based bootstrap as deprecated and remove it from the steady-state architecture. |
| C9 | Ingress choice is explicit in some docs (Kong) but only comparative/appendix-level in others (Gateway API, HAProxy). | A, E, P | **Kong wins as the current gateway.** Gateway API remains researchable as a control-surface standard; HAProxy is dropped. |
| C10 | The gitops doc defines a custom build-state model (`deployments`, `builds`, Redis aggregation, build topics) that may duplicate Buildkite capabilities. | G, P | **Conditional branch only.** Keep the custom build/event plane as an optional later phase, not as the default baseline. |
| C11 | Node scaling ownership is ambiguous: Karpenter, provider-native pool scaling, and VPS realities do not line up cleanly. | P | **No immediate commitment.** Defer node-autoscaler choice until provider research closes. |
| C12 | Build/debug UX is unresolved between Kibana and a bespoke frontend. | G, P | **Start with existing surfaces.** Use Buildkite UI + Kibana/Grafana first; only build a custom frontend after real operator pain proves the need. |
| C13 | Static environment management and dynamic environment management overlap heavily between `gitops.md` and `platform-v2.md`. | G, P | **Separate the lanes.** Static releases stay Git/Flux-driven; API/DB/Kafka flows are reserved for dynamic environments and are not allowed to redefine static GitOps. |

## 4. Unified dependency graph

Normalization rule:

- Use `A` auth units as the authoritative auth implementation path.
- Use `G` units as the authoritative environment-schema/API path.
- Use `P` and `E` units as the authoritative provider/bootstrap/hardening path.
- Overlapping `P` auth units and `G` custom-controller units are either aliases or conditional branches and are called out inline.

### 4.1 Foundation

- `foundation-vultr-bootstrap` -> none. Modernize this legacy unit to mean: OpenTofu provisions the provider/VPS base, base networking, DNS, and the initial cluster/object-storage primitives. The provider slot is `Vultr|Hetzner`.
- `management-cluster-bootstrap` -> `foundation-vultr-bootstrap`. Bootstrap the first Kubernetes control plane, Flux CD, and cluster add-on installation capability.
- `repo-layout-standardization` -> `management-cluster-bootstrap`. Canonical repo boundaries must exist before delivery automation lands.
- `gitops-static-repo-workflow` -> `repo-layout-standardization`. Static desired state must have a stable repo contract before release automation points at it.
- `flux-bucket-source` -> `management-cluster-bootstrap`. Resolve the legacy bucket terminology to a **Flux Git source** plus Kustomizations; keep the unit ID, modernize the implementation.
- `infisical-secrets` -> `management-cluster-bootstrap`. Secrets are foundational because almost every later unit consumes credentials.
- `crossplane-vultr-provider` -> `management-cluster-bootstrap`, `infisical-secrets`. Keep this branch marked `EVALUATE`; it only becomes real if dynamic environments still need provider CRDs.

### 4.2 Infrastructure

- `postgres-platform-db` -> `management-cluster-bootstrap`, `infisical-secrets`. Creates the production PostgreSQL surface.
- `db-environments-schema` -> `postgres-platform-db`. Environment-state contract lands on top of the DB.
- `db-deployments-schema` -> `postgres-platform-db`. Only needed for the optional custom build/event plane.
- `db-builds-schema` -> `db-deployments-schema`. Only needed if the custom build/event plane survives.
- `kafka-event-backbone` -> `management-cluster-bootstrap`, `infisical-secrets`. Central bus for environment/events/alerts.
- `harbor-registry` -> `management-cluster-bootstrap`, `infisical-secrets`. Registry must exist before delivery automation can ship artifacts.
- `observability-backends` -> `management-cluster-bootstrap`, `infisical-secrets`. Bring up metrics, logs, traces, and operator UIs early enough that later phases are observable.
- `network-calico-default-deny` -> `management-cluster-bootstrap`, `kong-ingress`. Network policy hardening depends on a working traffic path.
- `dr-velero-vultr-backups` -> `management-cluster-bootstrap`, `infisical-secrets`. Backup/restore is an infrastructure concern once stateful services exist.
- `linkerd-mesh` -> `management-cluster-bootstrap`, `infisical-secrets`. Optional service mesh branch.
- `edge-cloudflare-origin-lockdown` -> `kong-ingress`, `management-cluster-bootstrap`. Edge lockdown only makes sense once the origin exists.
- `app-autoscaling-keda` -> `kafka-event-backbone`, `management-cluster-bootstrap`. Event-driven application scaling layer.
- `node-autoscaling-karpenter` -> `foundation-vultr-bootstrap`, `crossplane-vultr-provider`. Conditional on provider support and on keeping the Crossplane branch.

### 4.3 Platform services

- `gitlab-runner-k8s` -> `management-cluster-bootstrap`, `infisical-secrets`. Modernize this unit to mean **Buildkite agents/runners on the cluster**.
- `dagger-pipeline-portability` -> `gitlab-runner-k8s`, `harbor-registry`. Modernize this unit to mean the reusable **Buildkite build/test/publish pipeline**.
- `gitops-release-promotion` -> `dagger-pipeline-portability`, `gitops-static-repo-workflow`, `flux-bucket-source`. This is the static-release handoff into Flux.
- `kong-ingress` -> `management-cluster-bootstrap`, `infisical-secrets`, `auth-authentik-mfa-oidc`. Keep the legacy unit ID, but treat it as the concrete Kong deployment and route layer underneath `auth-kong-identity-context`.
- `auth-secrets-infisical-sync` -> `infisical-secrets`. Auth-plane secrets piggyback on the cluster-wide Infisical baseline.
- `auth-authentik-core` -> `auth-secrets-infisical-sync`.
- `auth-authentik-mfa-oidc` -> `auth-authentik-core`.
- `auth-kong-identity-context` -> `auth-authentik-mfa-oidc`, `kong-ingress`. This is the authoritative ingress identity contract.
- `auth-pomerium-core` -> `auth-authentik-mfa-oidc`, `auth-secrets-infisical-sync`, `management-cluster-bootstrap`. This resolves the legacy `external:ingress-controller-ready` dependency to the cluster bootstrap path.
- `auth-stepca-core` -> `auth-authentik-mfa-oidc`, `auth-secrets-infisical-sync`.
- `auth-cedar-opal-core` -> `auth-secrets-infisical-sync`. Marked `EVALUATE` until the authz-engine research closes.
- `auth-opal-authentik-sync` -> `auth-authentik-core`, `auth-cedar-opal-core`. Only relevant if OPAL/Cedar survives.
- `auth-node-bootstrap-ca-trust` -> `auth-stepca-core`, `crossplane-vultr-provider`, `flux-bucket-source`. Conditional on keeping the Crossplane branch.
- `auth-pomerium-admin-ui-routes` -> `auth-pomerium-core`.
- `auth-pomerium-tcp-routes` -> `auth-pomerium-core`.
- `auth-jit-ssh-client-wrapper` -> `auth-pomerium-tcp-routes`, `auth-stepca-core`, `auth-node-bootstrap-ca-trust`.
- `auth-gitops-policy-pipeline` -> `auth-pomerium-core`, `gitlab-runner-k8s`, `flux-bucket-source`. Modernize the old Terraform-plan workflow into Buildkite + OpenTofu execution.
- `auth-observability-logging` -> `observability-backends`, `auth-pomerium-core`, `auth-stepca-core`.
- `auth-observability-alert-routing` -> `auth-observability-logging`, `kafka-event-backbone`, `alert-bus-automation`.
- `auth-breakglass-runbook` -> `auth-observability-alert-routing`.
- `environment-api-read-path` -> `db-environments-schema`, `auth-authentik-mfa-oidc`.
- `environment-api-write-path` -> `environment-api-read-path`, `db-environments-schema`, `auth-cedar-opal-core`. If app authz changes, this dependency moves with it.
- `debezium-environments-cdc` -> `db-environments-schema`, `kafka-event-backbone`.
- `platform-api` -> `postgres-platform-db`, `auth-kong-identity-context`, `environment-api-read-path`, `environment-api-write-path`. It optionally depends on `auth-cedar-opal-core` for fine-grained policy checks.
- `deployment-cdc-pipeline` -> `postgres-platform-db`, `kafka-event-backbone`, `debezium-environments-cdc`.
- `platform-deployer` -> `deployment-cdc-pipeline`, `crossplane-vultr-provider`, `harbor-registry`, `flux-bucket-source`. Conditional dynamic-environment bridge.
- `sue-ttl-cleanup` -> `platform-api`, `deployment-cdc-pipeline`, `platform-deployer`. Only matters if dynamic preview environments remain in scope.
- `component-contracts` -> `kong-ingress`, `observability-backends`, `gitops-release-promotion`. The expansion-plan contract layer should be treated as an implementation prerequisite, not hand-wavy future work.
- `ci-trivy-predeploy-scan` -> `component-contracts`, `gitlab-runner-k8s`.
- `cluster-trivy-continuous-scan` -> `component-contracts`, `management-cluster-bootstrap`, `infisical-secrets`.
- `runtime-falco-detection` -> `component-contracts`, `management-cluster-bootstrap`, `observability-backends`, `infisical-secrets`.
- `finops-opencost-integration` -> `component-contracts`, `observability-backends`.
- `telemetry-context-propagation` -> `platform-api`, `auth-kong-identity-context`, `kafka-event-backbone`, `postgres-platform-db`, `observability-backends`.
- `alert-bus-automation` -> `kafka-event-backbone`, `observability-backends`. Optional if StackStorm survives.

Conditional Buildkite-gap branch:

- `kafka-build-contracts` -> `db-builds-schema`, `kafka-event-backbone`.
- `debezium-builds-cdc` -> `db-builds-schema`, `kafka-build-contracts`.
- `orchestrator-deployment-registration` -> `db-deployments-schema`, `db-builds-schema`.
- `builder-execution-service` -> `kafka-build-contracts`, `debezium-builds-cdc`, `dagger-pipeline-portability`.
- `timeout-management-service` -> `kafka-build-contracts`.
- `deployment-ready-aggregation` -> `db-deployments-schema`, `db-builds-schema`, `kafka-build-contracts`, `orchestrator-deployment-registration`.
- `build-log-streaming` -> `builder-execution-service`.
- `elastic-ingest-enrichment` -> `db-builds-schema`, `build-log-streaming`.
- `debug-ui-build-traceability` -> `build-log-streaming`, `elastic-ingest-enrichment`.

### 4.4 Applications

- `auth-app-pep-integration` -> `auth-kong-identity-context`, `auth-cedar-opal-core`, `auth-opal-authentik-sync`. This is the application-side authz integration, and it should not be started until the engine choice is closed.
- `integration-validation-suite` -> `component-contracts`, `edge-cloudflare-origin-lockdown`, `ci-trivy-predeploy-scan`, `cluster-trivy-continuous-scan`, `runtime-falco-detection`, `network-calico-default-deny`, `dr-velero-vultr-backups`, `finops-opencost-integration`, `telemetry-context-propagation`.
- `pilot-application-onboarding` -> `integration-validation-suite`, `gitops-release-promotion`.
- `local-dev-simulation` -> `dagger-pipeline-portability`, `flux-bucket-source`, `harbor-registry`. Only worth doing after the delivery model stabilizes.
- `server-manager` -> `gitops-release-promotion`, `harbor-registry`, `postgres-platform-db`, `infisical-secrets`. Add `observability-backends` for production readiness; add `kong-ingress` only if the bot later exposes a public HTTP surface.

## 5. Modernized architecture summary

After modernization, the target stack looks like this:

### Foundation

- A low-cost VPS provider: `Vultr` or `Hetzner`.
- A self-managed Kubernetes cluster on that provider, bootstrapped by OpenTofu.
- Git repositories with PR review as the desired-state source.
- Flux CD plus Kustomizations as the reconciler.
- An ingress controller in-cluster.
- S3-compatible object storage for artifacts, backups, and any claim/output files that still need it.

### Infrastructure

- PostgreSQL plus `pg_stat_statements` as the source of truth.
- Harbor as the registry.
- Kafka and Debezium for asynchronous/event-driven flows.
- Infisical plus the InfisicalSecret/Operator sync path for secrets.
- VictoriaMetrics, vmagent, vmalert, and Prometheus-compatible exporters for metrics and alert production.
- Elasticsearch, Kibana, Elastic APM, and the ingest/enrichment pipeline for logs, traces, and RCA.
- Cloudflare at the public edge.
- Calico for network policy.
- Velero, Restic, and VolumeSnapshots for backup/restore.
- OpenCost for cost visibility.

### Platform services

- Buildkite for build/test/publish/deploy pipelines.
- Authentik plus OIDC/MFA/JWT federation for identity.
- Kong for public ingress and identity-header propagation.
- Pomerium and Pomerium API for operator/admin access.
- step-ca, SSH certificate trust, and the JIT client workflow for operator access.
- A FastAPI/Pydantic platform API for environment and control-plane operations.
- OPAL/Cedar or its replacement, once the authz research closes.
- Optional StackStorm automation, Linkerd, Crossplane, Platform Deployer, and Karpenter if later phases prove they earn their complexity.

### Applications

- `server-manager` as the immediate production workload.
- Later admin/API workloads and pilot applications consuming the same delivery, auth, observability, and security contracts.

The unresolved slots in the modernized architecture are narrow and explicit:

- provider = `Vultr` or `Hetzner`
- fine-grained app auth = `OPAL/Cedar` or `Casbin`
- infra abstraction = keep/drop `Crossplane`
- alert automation = keep/drop `StackStorm`

## 6. Critical path to Discord bot

The minimum production platform for `server-manager` is much smaller than the full platform.

Strict path:

1. `server-manager` needs a container image, deployment manifest, Discord token, and DB credentials.
2. That requires `harbor-registry`, `gitlab-runner-k8s` modernized to Buildkite agents, `dagger-pipeline-portability` modernized to Buildkite pipelines, and `gitops-release-promotion`.
3. Those delivery units require `management-cluster-bootstrap`, `foundation-vultr-bootstrap`, Git repos, Flux CD, and baseline secrets from `infisical-secrets`.
4. The bot's state path requires `postgres-platform-db`.
5. Production readiness adds `observability-backends` so failures are debuggable in a live Discord service.

Minimal dependency chains:

- Runtime chain: `server-manager` -> `gitops-release-promotion` -> `dagger-pipeline-portability` -> `gitlab-runner-k8s` -> `management-cluster-bootstrap` -> `foundation-vultr-bootstrap`
- Artifact chain: `server-manager` -> `harbor-registry` -> `management-cluster-bootstrap` -> `foundation-vultr-bootstrap`
- State/secret chain: `server-manager` -> `infisical-secrets` + `postgres-platform-db` -> `management-cluster-bootstrap` -> `foundation-vultr-bootstrap`

Not on the minimum bot path:

- Authentik
- Pomerium
- OPAL/Cedar
- Kafka
- Debezium
- Cloudflare
- Crossplane
- Linkerd
- Trivy/Falco/Calico
- Velero/OpenCost
- KEDA/Karpenter

Conditional add-on:

- If the bot later exposes a public API, add `kong-ingress` and then the auth-plane units that sit behind it.

This critical path should be treated as **Phase 1 platform buildout for the Discord bot**.

## 7. Phased implementation plan

### Phase 1: Foundation Bootstrap

- Components deployed: OpenTofu-managed provider base, Kubernetes cluster, Flux CD, Git repo layout, ingress controller, Infisical, base object-storage wiring.
- Dependencies satisfied: none.
- What becomes possible after this phase: the platform can accept GitOps-managed cluster add-ons and secrets-backed workloads.
- Estimated implementation units: about **7** legacy units.
- Primary unit anchors: `foundation-vultr-bootstrap`, `management-cluster-bootstrap`, `flux-bucket-source`, `repo-layout-standardization`, `gitops-static-repo-workflow`, `infisical-secrets`, `crossplane-vultr-provider` (only if retained).

### Phase 2: Bot Production Baseline

- Components deployed: PostgreSQL, Harbor, Buildkite agents/pipelines (modernized `gitlab-runner-k8s` and `dagger-pipeline-portability`), Flux release promotion, minimum observability, and the `server-manager` workload.
- Dependencies satisfied: Phase 1.
- What becomes possible after this phase: the Discord bot can run in production on the new platform with CI/CD, secrets, and durable storage.
- Estimated implementation units: about **6** legacy units plus the new `server-manager` workload.
- Primary unit anchors: `postgres-platform-db`, `harbor-registry`, `gitlab-runner-k8s`, `dagger-pipeline-portability`, `gitops-release-promotion`, `observability-backends`.

### Phase 3: Identity and Secure Operations

- Components deployed: Authentik, OIDC/MFA setup, Kong identity context, Pomerium, step-ca, admin-UI routes, JIT SSH client workflow, provider-agnostic break-glass runbook, and policy delivery pipeline.
- Dependencies satisfied: Phases 1-2 and working ingress.
- What becomes possible after this phase: audited operator access, protected internal UIs, and the first coherent identity plane.
- Estimated implementation units: about **12** legacy units.
- Primary unit anchors: `auth-secrets-infisical-sync`, `auth-authentik-core`, `auth-authentik-mfa-oidc`, `auth-kong-identity-context`, `auth-pomerium-core`, `auth-pomerium-admin-ui-routes`, `auth-pomerium-tcp-routes`, `auth-stepca-core`, `auth-node-bootstrap-ca-trust`, `auth-jit-ssh-client-wrapper`, `auth-gitops-policy-pipeline`, `auth-breakglass-runbook`.

### Phase 4: Dynamic Environment Control Plane

- Components deployed: environment schema, environment API read/write paths, Debezium/Kafka environment CDC, Platform Service API, Platform Deployer if retained, and TTL cleanup for temporary environments.
- Dependencies satisfied: Phases 1-2; Phase 3 if environment API uses the shared auth plane.
- What becomes possible after this phase: API-managed preview/test environments and DB-backed desired-state workflows.
- Estimated implementation units: about **9** legacy units.
- Primary unit anchors: `db-environments-schema`, `environment-api-read-path`, `environment-api-write-path`, `kafka-event-backbone`, `debezium-environments-cdc`, `platform-api`, `deployment-cdc-pipeline`, `platform-deployer`, `sue-ttl-cleanup`.

### Phase 5: Authorization and Telemetry Contracts

- Components deployed: chosen fine-grained authorization engine, app-side policy enforcement, auth observability, OpenTelemetry context propagation, and alert bus wiring.
- Dependencies satisfied: Phases 2-4.
- What becomes possible after this phase: application-level policy enforcement and correlated RCA across ingress, app, Kafka, and Postgres.
- Estimated implementation units: about **9** legacy units.
- Primary unit anchors: `auth-cedar-opal-core`, `auth-opal-authentik-sync`, `auth-app-pep-integration`, `auth-observability-logging`, `auth-observability-alert-routing`, `telemetry-context-propagation`, `alert-bus-automation`, `component-contracts`, `auth-gitops-policy-pipeline`.

### Phase 6: Hardening, Recovery, and Cost

- Components deployed: Cloudflare edge, Trivy CI and cluster scans, Falco, Calico default-deny, Velero backup/restore, OpenCost, and the validation suite.
- Dependencies satisfied: Phases 2-5.
- What becomes possible after this phase: hardened edge posture, tested restore path, runtime security signals, and cost visibility.
- Estimated implementation units: about **8** legacy units.
- Primary unit anchors: `edge-cloudflare-origin-lockdown`, `ci-trivy-predeploy-scan`, `cluster-trivy-continuous-scan`, `runtime-falco-detection`, `network-calico-default-deny`, `dr-velero-vultr-backups`, `finops-opencost-integration`, `integration-validation-suite`.

### Phase 7: Advanced Build/Event Control Plane

- Components deployed: the optional custom build-state model, build topics, builder workers, timeout watcher, enriched build logs, and a build-debug surface.
- Dependencies satisfied: Phases 1-3 and a prior decision that Buildkite does **not** cover the required behavior.
- What becomes possible after this phase: platform-native build/event orchestration and richer build-traceability than Buildkite alone.
- Estimated implementation units: about **9** legacy units.
- Primary unit anchors: `db-deployments-schema`, `db-builds-schema`, `kafka-build-contracts`, `debezium-builds-cdc`, `orchestrator-deployment-registration`, `builder-execution-service`, `timeout-management-service`, `deployment-ready-aggregation`, `build-log-streaming`, `elastic-ingest-enrichment`, `debug-ui-build-traceability`.

### Phase 8: Local Simulation and Pilot Onboarding

- Components deployed: high-fidelity local harness and a pilot application on the hardened platform.
- Dependencies satisfied: Phases 2-7, depending on how much of the advanced build plane survives.
- What becomes possible after this phase: safe, repeatable end-to-end rehearsal and a real non-bot workload validating the full platform.
- Estimated implementation units: about **3** legacy units.
- Primary unit anchors: `local-dev-simulation`, `pilot-application-onboarding`, plus any final `integration-validation-suite` follow-up work.

## 8. Open research questions

- **OPAL/Cedar vs Casbin**: legacy docs assume OPAL/Cedar, but the user explicitly reopened the decision. Research has to cover policy expressiveness, cache/distribution model, runtime latency, Python ergonomics, and operational burden.
- **Hetzner vs Vultr for VPS-hosted Kubernetes**: compare cost, egress, node shapes, load-balancing story, object storage, managed DB options, support quality, and autoscaling constraints.
- **Buildkite vs the legacy custom build/event plane**: decide whether Buildkite already covers build orchestration, logs, timeouts, approvals, and artifact promotion strongly enough to delete the `db-deployments`/`db-builds`/builder-service branch.
- **Paginated protected results without re-querying**: this needs a dedicated auth/caching design pass because it cuts across app auth, data-layer policy, pagination stability, and cache invalidation.
- **Crossplane's role after OpenTofu**: determine whether dynamic environments really justify keeping Crossplane, or whether OpenTofu + Flux + HelmRelease/Kustomize primitives are sufficient.
- **Flux source of truth for dynamic artifacts**: re-evaluate whether any bucket-backed claim flow is still necessary once Git is the canonical desired-state source.
- **Kafka + Debezium minimum viable use**: decide whether the one-person + agent ops model should keep the full CDC/event-bus design or push some early phases toward simpler Postgres-native workflows.
- **Linkerd and Karpenter fit on the chosen provider**: both are useful, neither is phase-1 critical, and both can introduce ops overhead if provider support is weak.
- **Break-glass implementation on the chosen provider**: rework the Vultr-specific portal/audit assumptions into a provider-neutral runbook and confirm audit export options.

## 9. Risk flags

- **Complexity budget**: even after collapsing duplicates, this is still a large program. The legacy indexes total 76 implementation units before modernization, and the surviving set is still substantial.
- **Skills breadth**: the plan spans Kubernetes bootstrap, provider networking, CI/CD, GitOps, identity, secrets, observability, security hardening, and backup/restore. That is a wide surface for a one-person + agent team.
- **Cost model drift**: the modernization reduces hosting cost compared with Railway Pro + Supabase, but self-hosting adds hidden costs in operations time, backup storage, and observability retention.
- **Operational burden**: Kafka, Debezium, Authentik, Pomerium, Harbor, Infisical, Elastic, and VictoriaMetrics are all real operational systems. The platform can easily become too heavy before it creates enough value.
- **Vendor lock-in vectors**: provider-specific autoscaling, object storage plugins, break-glass procedures, and audit-log integration can reintroduce lock-in even after moving off Railway/Supabase.
- **Control-plane overlap risk**: OpenTofu, Flux, Crossplane, and any surviving custom deployer/controller can create split-brain ownership unless the boundaries are explicitly constrained.
- **Current-state divergence**: this repo's `DECISIONS.md` still locks the live bot MVP to Railway + Supabase. Moving the Discord bot onto this platform is a separate decision and migration project, not an automatic consequence of this index.
