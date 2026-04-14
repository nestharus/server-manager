## 1. Scope and document intent

`platform-v2.md` is a legacy platform specification for a Kubernetes-based internal platform, framed around a Vultr-hosted control plane and workload fleet. It behaves as a combined vision/spec/implementation sketch: it sets platform goals, fixes a named technology stack, defines key integration handoffs and contracts, and describes representative operational workflows and persona use cases. It covers cloud/orchestration, bootstrap, GitOps, CI/CD, dynamic environment provisioning, security and identity, observability, alert-driven automation, and autoscaling. It does not fully specify individual service internals, ownership boundaries, or modernization-era substitutions; those remain merge-time concerns.

## 2. Component inventory

| Component | Kind | Role in document | Notes |
| --- | --- | --- | --- |
| Vultr Kubernetes Platform | Internal platform | Primary subject of the document | Explicit legacy platform name and scope anchor. |
| Vultr | Cloud provider | Underlying infrastructure provider | Explicit provider choice; later sections assume direct Vultr API integration. |
| Vultr Kubernetes Engine (VKE) | Managed Kubernetes service | Cluster substrate for management and workload clusters | Explicitly central to both bootstrap and runtime flows. |
| management VKE cluster | Internal subsystem | Hosts the declarative control plane and CI runner | Explicit in bootstrap and dynamic environment flows. |
| VKE workload cluster | Internal subsystem | Target cluster for application deployment | Explicit in static deployment flow; distinct from management cluster. |
| dual-VPC DMZ networking | Network topology | Foundational network layout provisioned at bootstrap | Explicitly named once; rationale is not expanded. |
| Terraform | IaC tool | Day 0 provisioning entrypoint | Explicitly the first bootstrap tool. |
| Ansible | Automation tool | Installs initial control-plane components after Terraform | Explicitly the bridge from imperative bootstrap to declarative control plane. |
| bastion host | Access host | Execution point for the bootstrap playbook | Explicitly named in bootstrap sequence; not otherwise defined. |
| Crossplane | Control-plane framework | Day 1+ infrastructure reconciliation | Explicitly manages later infrastructure state against Vultr. |
| VKECluster (`platform.vultr.com/v1alpha1`) | Custom resource | High-level declaration of a Vultr Kubernetes cluster | Explicit schema contract; strongly provider-specific. |
| FluxCD | GitOps engine | Reconciles Kubernetes manifests for platform and app delivery | Explicitly used with both object storage and Git repository sources. |
| Vultr Object Storage | Object storage service | GitOps source of truth for management/bootstrap and dynamic claims | Explicitly used as a Flux source and dynamic claim drop location. |
| GitOps repository | Repository subsystem | Source for static deployment manifests | Explicitly separate from application repositories. |
| GitLab / GitLab CI | SCM and CI control plane | Triggers merge-based deployment pipeline | Explicitly named in static deployment workflow. |
| Self-Hosted GitLab Runner (Kubernetes Executor) | CI runner | Executes CI jobs inside the management cluster | Explicitly named as CI/CD engine. |
| Dagger | Pipeline engine | Defines portable CI/CD and local workflow logic | Explicitly central to remote CI and local simulation. |
| FastAPI | API framework | Basis of the Platform Service API | Explicitly named in the stack and integration flows. |
| Platform Service | Internal service | API for dynamic environment lifecycle operations | Explicit service boundary; endpoints are partially specified. |
| PostgreSQL | Database | Primary state store for Platform Service | Explicitly stores environment request state. |
| deployments table | Database table | Source table for deployment CDC events | Explicitly named in the Debezium flow; schema is only partially described. |
| Debezium | CDC system | Converts database changes into deployment events | Explicitly tied to PostgreSQL WAL capture. |
| Apache Kafka | Event bus | Carries deployment requests and operational alerts | Explicit shared bus for provisioning and AIOps pipelines. |
| `platform-deployment-requests` | Kafka topic | Durable channel for environment provisioning requests | Explicit topic name and event contract. |
| Platform Deployer | Internal microservice | Consumes deployment events and writes generated claims/artifact references | Explicitly named in flow sections only. |
| Self-Hosted Harbor | Artifact repository | Stores versioned application and infrastructure artifacts | Explicitly described as definitive repository. |
| Docker image / OCI infrastructure artifact | Build artifact | Deployment output of application pipelines | Explicitly immutable and version-tagged; local workflow also says "OCI playbook". |
| Self-Hosted Authentik | Identity provider | Exclusive identity source and sole OIDC provider | Explicitly tied to MFA and identity centralization. |
| Pomerium | Identity-aware access proxy | Governs sensitive infrastructure access and internal UIs | Explicitly paired with ZTNA and JIT access. |
| OIDC | Identity protocol | Auth protocol between Authentik and access layers | Explicitly required for Pomerium re-authentication; implied for Kong validation path. |
| JWT bearer token | Token format | Credential validated at the application gateway | Explicitly validated by Kong for app access. |
| OPAL/Cedar | Authorization engine | Fine-grained policy decision layer | Explicitly used for application and data-plane authorization. |
| Smallstep step-ca | Certificate authority | Issues short-lived SSH credentials | Explicitly used for JIT infrastructure access. |
| SSH certificate | Credential artifact | Ephemeral per-session credential for infra access | Explicitly minted by step-ca. |
| Self-Hosted Infisical | Secrets manager | Exclusive platform secret store | Explicitly described as centralized and declarative. |
| InfisicalSecret | Custom resource | Declarative request for secrets materialization into Kubernetes | Explicit CRD contract; depends on an Infisical Operator that is only implied here. |
| Kong API Gateway | API gateway | Governs public-facing API traffic and injects identity headers | Explicitly part of the application access path. |
| Linkerd | Service mesh | Named networking component for service-to-service communication | Explicit stack choice; not deeply integrated elsewhere in the document. |
| VictoriaMetrics | Metrics backend | Metrics storage and alert-source component | Explicitly part of unified observability. |
| `vmalert` | Alerting component | Emits structured alerts into Kafka | Explicitly named producer within the alert pipeline. |
| Elasticsearch | Logs backend | Stores/query logs and participates in alerting and debugging workflows | Explicitly part of observability and anomaly detection flow. |
| Elastic APM | Trace backend | Stores/displays distributed traces | Explicitly paired with Elasticsearch in the stack and SRE workflow. |
| Elasticsearch Anomaly Detection | Alerting component | Produces alert events to Kafka | Explicitly named only in alert pipeline. |
| OpenTelemetry | Telemetry standard | Standard for instrumentation and context propagation | Explicitly required for unified observability and Kafka/app instrumentation. |
| `platform-alerts` | Kafka topic | Central alert bus | Explicit topic name and alert contract. |
| StackStorm | Automation engine | Consumes alerts and runs remediation workflows | Explicit AIOps executor. |
| KEDA | Autoscaler | Drives event-based application scaling | Explicitly watches Kafka consumer lag and feeds HPA. |
| KEDA ScaledObject | Custom resource | Declarative KEDA scaling contract | Explicit schema item; links workload to external triggers. |
| Horizontal Pod Autoscaler (HPA) | Kubernetes controller | Acts on KEDA-provided metrics to scale workloads | Explicitly named in scaling chain. |
| Karpenter | Node autoscaler | Provisions nodes in response to unschedulable pods | Explicitly calls the Vultr API in the scaling chain. |
| Flink Adaptive Scheduler | Stateful autoscaler | Adjusts parallelism inside Flink jobs | Explicitly named as the stateful scaling layer. |
| Kind | Local Kubernetes distro | Simulates a cluster for local end-to-end testing | Explicitly central to local high-fidelity workflow. |
| Self-Hosted MinIO | Local object storage | Local S3-compatible backing store for GitOps testing | Explicit local substitute for object storage. |
| Kustomization / HelmRelease | GitOps manifest types | Example manifest forms updated by the pipeline | Explicitly named as artifact-reference update targets. |
| Grafana | Observability UI | Used by the SRE persona for metrics and database dashboards | Explicitly appears in the debugging use case, not in the core stack table. |
| Kibana | Observability UI | Used by the SRE persona for log investigation | Explicitly appears in the debugging use case. |
| `pg_stat_statements` | PostgreSQL extension | Source of `query.id` observability attribute | Explicitly required for normalized SQL query identification. |

## 3. Architectural decisions

| Decision | Evidence from document | Rationale in document | Confidence | Modernization risk |
| --- | --- | --- | --- | --- |
| Use a single identity-driven control plane for all access domains | Section 1.1 says a single identity-driven policy/control plane governs all access; Section 3.1 unifies Authentik, OPAL/Cedar, and Infisical | Correlate every action to a verified identity and avoid fragmented trust models | explicit | medium |
| Adopt Zero Trust Network Access instead of topology-based trust | Section 1.1 explicitly forbids trust based on being inside a VPC; Section 3.1 routes infra access through Pomerium | Eliminate perimeter-based trust and require per-request authn/authz | explicit | low |
| Use Just-in-Time access with short-lived credentials | Section 1.1 defines JIT access; Section 3.1 uses step-ca to mint short-lived SSH certificates | Remove standing privileges and shrink blast radius from credential theft | explicit | medium |
| Anchor the platform on Vultr and Vultr Kubernetes Engine | Section 2.1 names Vultr and VKE; Sections 4-6 repeatedly depend on Vultr API, VKE clusters, and Vultr Object Storage | Keep provisioning and reconciliation centered on one provider API and managed Kubernetes offering | explicit | high |
| Split infrastructure lifecycle responsibilities across Terraform, Ansible, and Crossplane | Section 2.2 assigns Day 0 to Terraform, initial install to Ansible, Day 1+ to Crossplane; Section 4.1 sequences them | Transition from imperative bootstrap into declarative self-management | explicit | medium |
| Make GitOps the foundation for infrastructure and application configuration | Section 1.2 requires declarative management; Sections 3.2, 4.1, and 4.3 describe Flux-driven reconciliation | Ensure changes are version-controlled, automated, and auditable | explicit | low |
| Support two environment lifecycle models: API-managed dynamic envs and Git-managed static envs | Section 1.2 defines a dual-model environment strategy; Sections 4.2 and 4.3 give separate flows | Optimize for both fast ephemeral environments and controlled prod/stage promotion | explicit | medium |
| Use FluxCD as the GitOps reconciler for both management and workload operations | Section 2.3 names FluxCD; Sections 4.1, 4.2, and 4.3 all rely on Flux reconciliation | Provide continuous reconciliation for control-plane bootstrap, claims, and app deployment | explicit | low |
| Use Dagger as the portability layer for CI and local workflows | Section 1.2 requires portable CI logic; Sections 3.2, 4.3, and 6.3 make Dagger the shared execution model | Keep pipeline logic identical locally and remotely to eliminate environment drift | explicit | high |
| Run CI execution inside the management cluster via self-hosted GitLab Runner | Section 2.3 picks Self-Hosted GitLab Runner; Section 4.3 places runner pods in the management cluster | Keep CI close to the platform and automate image/artifact publication from inside Kubernetes | explicit | high |
| Implement dynamic environment provisioning as an asynchronous event-driven pipeline | Section 3.2 says FastAPI, PostgreSQL, Debezium, and Kafka form the core; Section 4.2 describes the exact handoff chain | Decouple user-facing API latency from long-running provisioning | explicit | medium |
| Represent environment creation intent in PostgreSQL and derive events from CDC | Section 4.2 inserts a database record, then Debezium captures WAL changes into Kafka | Persist the request durably before provisioning begins | explicit | medium |
| Generate declarative claim files rather than provisioning environments directly from the API | Section 4.2 has Platform Deployer write JSON claims for Crossplane and FluxCD into object storage | Preserve declarative control and keep long-running reconciliation in platform controllers | explicit | medium |
| Use a decoupled trust model with separate gateways for application traffic and infrastructure access | Section 3.1 explicitly names Kong for app access and Pomerium for infrastructure access | Prevent application credentials from being useful for infrastructure compromise | explicit | medium |
| Propagate identity context from Kong into downstream systems using standardized headers | Section 3.1 injects `x-user-id` and `x-environment-id`; Section 5.4 formalizes the attributes | Make authorization and observability context available beyond the ingress boundary | explicit | medium |
| Re-authenticate each infrastructure session and mint separate SSH credentials | Section 3.1 says Pomerium forces interactive OIDC re-authentication and step-ca issues single-use SSH certs | Enforce ZTNA and JIT for sensitive access paths | explicit | medium |
| Centralize secrets in Infisical and fetch them declaratively into Kubernetes | Section 2.5 makes Infisical exclusive; Section 5.2 defines `InfisicalSecret` materialization into native `Secret` objects | Maintain a single auditable secret source and GitOps-friendly workflow | explicit | medium |
| Treat Harbor as the definitive artifact repository for both app and infrastructure artifacts | Section 3.2 says Harbor is definitive and stores container images plus OCI infra artifacts; Sections 4.2, 4.3, and 6.1 consume from Harbor | Make deployments repeatable and traceable from immutable artifacts | explicit | medium |
| Use immutable artifact tags such as Git commit SHA in deployment flows | Section 4.3 says artifacts are tagged with an immutable identifier such as commit SHA | Keep release provenance and rollback references stable | explicit | low |
| Define a unified observability contract around OpenTelemetry-enriched metrics, logs, and traces | Section 1.3 requires unified observability; Section 3.3 names OpenTelemetry + VictoriaMetrics + Elasticsearch; Section 5.4 defines required attributes | Enable user-centric debugging across the full request path | explicit | medium |
| Use Kafka as a shared event bus for both provisioning and operational alerting | Sections 3.2 and 3.3 use Kafka for deployment and alert buses; Sections 4.2 and 4.4 define both topics | Centralize durable asynchronous events for platform automation | explicit | medium |
| Drive remediation through StackStorm rules/workflows fed by Kafka alerts | Section 3.3 says Kafka plus StackStorm create the AIOps pipeline; Section 4.4 formalizes sensor-trigger-rule-action flow | Enable automated investigation and remediation from structured alerts | explicit | medium |
| Implement autoscaling as a layered causal chain across workload, node, and stateful layers | Section 1.3 requires multi-layered elasticity; Sections 3.3 and 6.4 compose KEDA, HPA, Karpenter, and Flink Adaptive Scheduler | Match resources to demand at multiple layers for cost and responsiveness | explicit | medium |
| Enforce a default 24-hour TTL for `sue` environments | Section 6.2 defines a scheduled cleanup job for `sue` environments after 24 hours; Section 7.1 repeats the behavior | Keep temporary environments ephemeral and self-cleaning | explicit | medium |
| Standardize static deployments as zero-downtime rolling updates driven by Flux | Sections 4.3 and 6.1 both end in Flux-applied rolling updates on the workload cluster | Preserve auditability while avoiding downtime during release | explicit | low |

## 4. Implementation units

| Unit | What would need to be built/configured | Dependencies | Why it exists |
| --- | --- | --- | --- |
| Vultr base infrastructure bootstrap | Provision management VKE cluster, dual-VPC DMZ networking, and Vultr Object Storage via Terraform | Vultr API, Terraform credentials, VKE, object storage | Creates the initial substrate the rest of the platform assumes exists. |
| Terraform output handoff | Emit kubeconfig and related connection data for downstream bootstrap consumers | Terraform state/output conventions | Allows later bootstrap stages to connect to the newly created cluster. |
| Bastion-driven bootstrap playbook | Run Ansible from a bastion host to install Crossplane and FluxCD Helm charts into the management cluster | Bastion host, kubeconfig, Ansible, Helm charts | Transitions the platform from Day 0 provisioning into declarative control. |
| Crossplane Vultr provider setup | Configure provider credentials, provider packages, and the control-plane objects needed to reconcile Vultr resources | Crossplane, Vultr API, management cluster | Lets the platform manage later infrastructure declaratively instead of by imperative scripts. |
| `VKECluster` abstraction | Define or adopt the provider-specific cluster claim abstraction used by platform automation | Crossplane, Vultr provider, CRD packaging | Gives the platform a higher-level interface for workload cluster creation. |
| Flux source wiring | Configure FluxCD to watch the correct source locations in Vultr Object Storage and the GitOps repository | FluxCD, object storage access, Git credentials | Makes declarative artifacts discoverable by the reconciler. |
| GitOps repository layout and manifests | Define the repository structure and manifest objects updated during static deploys | GitOps repository, Kustomization/HelmRelease conventions, FluxCD | Provides the auditable source of static environment configuration. |
| Platform Service API surface | Implement `POST /environments`, `GET /environments`, and `DELETE /environments/{name}` plus request/response handling | FastAPI, Authentik, OPAL/Cedar | Exposes the developer/operator entrypoint for dynamic environments. |
| Platform Service persistence model | Create PostgreSQL schema for deployment/environment records, including fields referenced in the event contract | PostgreSQL, API contracts, quotas/auth rules | Stores durable environment intent and lifecycle state. |
| Debezium CDC pipeline | Configure Debezium to capture changes from the PostgreSQL WAL for the deployments table | PostgreSQL WAL access, Debezium connector runtime | Converts durable DB state changes into async provisioning events. |
| Kafka provisioning channel | Provision brokers/topics/config needed for `platform-deployment-requests` delivery | Apache Kafka, Debezium, Platform Deployer | Carries environment requests to the provisioning worker. |
| Platform Deployer service | Consume deployment events, resolve required artifacts, and generate final Crossplane/Flux claim files | Kafka, Harbor, Vultr Object Storage, claim schema | Bridges platform intent records into declarative runtime inputs. |
| Claim file generation contract | Define the JSON claim files written for Crossplane and FluxCD per environment | Platform Deployer, Crossplane, FluxCD | Gives dynamic provisioning a concrete handoff artifact. |
| Dynamic environment reconciliation path | Ensure new claims placed in object storage trigger workload cluster creation and app deployment | FluxCD, Crossplane, object storage, management cluster | Turns environment requests into actual provisioned environments. |
| Harbor deployment and policy | Deploy Harbor and define artifact publication/retention/tagging expectations | Harbor, storage, CI pipelines | Centralizes immutable application and infrastructure artifacts. |
| In-cluster CI runner deployment | Run self-hosted GitLab Runner pods with the Kubernetes executor inside the management cluster | GitLab, management cluster, runner registration | Provides the remote CI execution plane assumed by the document. |
| Dagger pipeline definitions | Author portable pipeline code for publish, test, and local environment commands | Dagger, GitLab Runner, Harbor, GitOps repo | Unifies local and remote pipeline behavior. |
| Static deployment manifest updater | Update GitOps repository manifests to point at newly published artifact tags | Dagger, GitOps repository, Harbor artifact metadata | Connects build outputs to GitOps-driven rollout. |
| Authentik identity plane | Deploy/configure Authentik with MFA and OIDC roles for humans and services | Authentik, user/service identity model | Establishes the single identity source assumed across the platform. |
| Kong application access path | Configure JWT validation, header injection, and ingress handling for public API traffic | Kong, Authentik, JWT claims, route mapping | Ensures verified identity arrives at application services. |
| Pomerium plus step-ca infrastructure access path | Configure re-authenticated infra access and on-demand SSH cert minting | Pomerium, Authentik, OIDC, step-ca | Implements ZTNA and JIT for sensitive infrastructure access. |
| OPAL/Cedar policy plane | Define policy distribution/evaluation setup for application and data-plane authorization | OPAL/Cedar, identity/context attributes | Supplies fine-grained authz decisions referenced by the API and platform flows. |
| Infisical secret delivery | Deploy Infisical and the operator path that resolves `InfisicalSecret` resources into Kubernetes Secrets | Infisical, operator/controller, workload namespaces | Makes secret distribution declarative and centralized. |
| Linkerd service mesh rollout | Install/configure Linkerd where service-to-service policy/telemetry is expected | Linkerd, workload clusters | Realizes the named service-mesh layer in the stack. |
| Telemetry context propagation | Instrument services and Kafka clients to emit required attributes such as `environmentId`, `userId`, `route`, `topic`, and `query.id` | OpenTelemetry, Kong, application middleware, Kafka clients, PostgreSQL exporter | Fulfills the document's observability contract. |
| Observability backends | Deploy VictoriaMetrics, Elasticsearch, and Elastic APM with the expected ingestion/query paths | Metrics/log/trace emitters, storage, dashboards | Stores and exposes the telemetry required for debugging and alerting. |
| Alert production and automation | Configure `vmalert`, Elasticsearch Anomaly Detection, Kafka alert publishing, StackStorm sensors, rules, and workflows | VictoriaMetrics, Elasticsearch, Kafka, StackStorm | Implements the proactive AIOps pipeline. |
| Application autoscaling definitions | Create KEDA `ScaledObject` resources and HPA-linked scaling rules for workloads | KEDA, external metrics such as Kafka lag, target Deployments | Lets workloads scale with event pressure. |
| Node autoscaling integration | Configure Karpenter to observe unschedulable pods and provision matching nodes on Vultr | Karpenter, Vultr API, cluster scheduling constraints | Supplies node capacity when workload scaling exceeds current cluster resources. |
| Stateful scaling integration | Enable Flink Adaptive Scheduler where stateful stream-processing workloads exist | Flink jobs, cluster capacity, job topology | Provides the stateful layer of the multi-layer autoscaling strategy. |
| Local high-fidelity simulation | Stand up Kind, local FluxCD, local Harbor, and MinIO-backed GitOps flows via Dagger commands | Dagger, Kind, MinIO, Harbor, FluxCD | Gives developers an end-to-end local rehearsal environment. |
| Dynamic environment TTL cleanup | Implement the scheduled cleanup path that deletes expired `sue` records and triggers teardown | Platform Service DB, scheduling, teardown event path | Enforces the document's default ephemerality policy for temporary environments. |
| SRE investigation surface | Provide the dashboards/log/trace/query drilldown path implied by the Grafana, Kibana, Elastic APM, and `query.id` workflow | Grafana, Kibana, Elastic APM, PostgreSQL metrics | Supports the debugging workflow described for operators. |

## 5. Cross-document dependencies

| Dependency | Depends on what | Why it is cross-document | Confidence |
| --- | --- | --- | --- |
| Security model and identity boundaries | `auth-v5.md` / "Auth v5" | The document cites "Auth v5" as its only works-cited source and repeatedly depends on prior identity/security decisions rather than redefining them here | high |
| GitOps repository structure and conventions | Likely a separate GitOps spec, potentially `gitops.md` | This document assumes a dedicated GitOps repository, manifest update mechanics, and Flux source wiring, but does not define repository shape or conventions in detail | medium |
| Application repository pipeline contracts | Application repos and their Dagger/GitLab definitions | Static delivery depends on application repos exposing the expected pipeline entrypoints and artifact outputs | high |
| Platform CLI/UI clients | A separate client/UI specification | Dynamic environment workflows assume a CLI or UI exists to call the Platform Service, but neither client contract is defined here | high |
| Authorization policies and quotas | Policy documents/models outside this file | The API flow references authorization policies and quotas, but the policy model, quota schema, and ownership are not specified here | high |
| Crossplane provider/composition layer | Provider packages and composition definitions outside this file | `VKECluster` is described as a high-level abstraction, but the compositions/provider mapping that make it real are not included | high |
| Secret operator behavior | Infisical operator/controller implementation docs | `InfisicalSecret` behavior assumes an operator that is not otherwise defined in this document | high |
| Deployment artifact contract | Build/release specification outside this file | Harbor is assumed to contain app images and OCI infrastructure artifacts, but the artifact formats and producers are only lightly described | medium |
| Observability dashboards and UX | Separate observability/dashboard definitions | Grafana and Kibana are used in the SRE workflow, but dashboard taxonomy, links, and ownership are not defined here | high |
| Alert destinations and operator notification channels | ChatOps/on-call integration outside this file | Use cases mention alerts arriving in a designated channel, but routing targets and escalation paths are not defined here | high |
| DNS/TLS/ingress for provisioned environments | Networking/ingress specification outside this file | Dynamic env flows say a URL is returned to the developer, but the DNS, certificate, and ingress path are omitted | high |
| Local-development parity rules | Separate dev-experience spec | The local "high-fidelity" workflow names a subset of components but does not define what is stubbed, omitted, or simulated relative to production | medium |
| Bootstrap execution environment | External operator runbook or infrastructure admin doc | The document assumes a bastion-host-based bootstrap and access to run Terraform/Ansible, but not how that environment is managed | medium |
| Stateful stream-processing workloads | A workload/application architecture document | Flink Adaptive Scheduler is chosen, but the actual Flink jobs and their platform role are not defined here | medium |

## 6. Outdated or questionable items

| Item | Why questionable | Likely modernization direction |
| --- | --- | --- |
| Dagger as the core CI/local orchestration layer | User override says `Buildkite` is the preferred modernization target over `Dagger`; this document makes Dagger central to CI, release, and local workflows | Preserve as a conflict marker and expect Buildkite-oriented replacement or major reduction of Dagger scope |
| GitLab / self-hosted GitLab Runner centric CI flow | The legacy spec couples CI execution to GitLab and runner pods in the management cluster, which may not survive if CI moves toward Buildkite or another control plane | Treat GitLab coupling as provisional and re-evaluate CI ownership/model during merge |
| Vultr-specific provider framing | User override says provider choice may move beyond the original Vultr framing; the document is deeply coupled to Vultr APIs, VKE, and Vultr Object Storage | Preserve provider coupling as a legacy assumption, not a modernization constraint |
| `VKECluster` provider-specific abstraction | The custom resource is explicitly bound to `platform.vultr.com/v1alpha1`, making the cluster abstraction non-portable | Replace or wrap with a provider-agnostic cluster/environment contract if the merged platform broadens providers |
| Flux source-of-truth split across object storage and Git repository | Management/bootstrap and dynamic environments use Vultr Object Storage as a Flux source, while static deployments use a GitOps repo; the split is real but not justified | Reconcile source-of-truth strategy during merge rather than assuming both survive unchanged |
| Node autoscaling ownership | The stack declares Karpenter as node autoscaler, but the `VKECluster` schema also includes Vultr native `auto_scaler`; that creates overlapping ownership | Resolve toward one authoritative node autoscaling model |
| Karpenter directly provisioning Vultr VMs | The scaling chain assumes Karpenter can directly call the Vultr API for optimally sized instances; provider/runtime support may differ in a modernized platform | Re-check provider support and potentially redesign node scaling abstraction |
| StackStorm as the automation engine | StackStorm is an older automation choice and the document gives it significant remediation responsibility without discussing alternatives or operational cost | Reassess automation/orchestration engine choice during modernization |
| Debezium + Kafka for environment provisioning | The provisioning path introduces a relatively heavy CDC/event stack for an environment-lifecycle API; the tradeoff is not defended beyond decoupling | Re-evaluate whether the merged platform still needs CDC-backed provisioning complexity |
| Flink Adaptive Scheduler as a first-class platform primitive | Stateful autoscaling is specified around Flink, but no workload context justifies why Flink is a platform-wide concern | Keep only if merged workload requirements still need Flink-specific scaling |
| Bastion-host-based bootstrap | The bootstrap sequence assumes Ansible runs from a bastion host, but long-term operational ownership and security posture of that host are not described | Prefer a more explicitly managed bootstrap/control path if possible |
| Local "high-fidelity" environment claim | The local simulation names Kind, Harbor, MinIO, and Flux, but omits many security/data-plane components while still claiming high fidelity | Narrow the claim or broaden the local model explicitly in the merged design |
| Self-hosted security/control-plane sprawl | Authentik, Pomerium, step-ca, Infisical, Harbor, Kafka, StackStorm, and observability backends add substantial self-hosted operational surface | Reassess which control-plane services remain self-hosted in the modern platform |
| Artifact naming inconsistency | Static pipeline says "OCI infrastructure artifact"; local workflow says "OCI playbook" for what appears to be the same concept | Normalize artifact vocabulary and contract during merge |
| Flux vs potential alternative GitOps engines | User override says `Flux` is the preferred modernization target over `Argo`; this file already uses Flux, but later merge conflicts may reintroduce Argo assumptions from other legacy docs | Preserve `Flux` preference as an explicit conflict marker in the merged index set |
| Entire document as a modernization baseline | User override says the modernized platform will likely differ materially from these legacy specs; this file is therefore an input artifact, not a target architecture | Use this index as evidence inventory, not as direct implementation guidance |

## 7. Missing or underspecified elements

| Gap | Why it matters | Confidence |
| --- | --- | --- |
| Management-cluster versus workload-cluster topology details | The document distinguishes the two but never fully defines how many clusters exist, how they are isolated, or how lifecycle ownership is divided | high |
| Crossplane compositions behind `VKECluster` | The CRD schema is partial, but the actual compositions/templates/provider mappings needed to make it usable are absent | high |
| Flux authentication and source configuration details | Flux watches both Vultr Object Storage and a Git repository, but auth, source objects, and layout conventions are not specified | high |
| Platform Service data model beyond event fields | The API and event contract mention some fields, but there is no full schema for environment state, statuses, ownership, or quotas | high |
| Platform Deployer idempotency, retries, and error reporting | This service is crucial to provisioning, yet failure modes and reconciliation semantics are not described | high |
| Environment DNS, ingress, and certificate issuance | Use cases assume developers receive a URL, but the network and certificate path to make that true is omitted | high |
| De-provisioning event contract | `DELETE /environments/{name}` exists, but the teardown event/schema/path is not described with the same specificity as create | high |
| Authorization policy model and quota rules | Authentik and OPAL/Cedar are named, but there is no policy schema, resource model, or quota decision surface | high |
| Workload identity model | Human identity is explicit, but service/workload identity beyond generic "service identities" is not operationally specified | high |
| Secret rotation and namespace scoping behavior | `InfisicalSecret` says secrets become native Kubernetes Secrets, but rotation semantics and namespace boundaries are not defined | high |
| Linkerd's actual role in traffic, identity, or policy | Linkerd is a named service mesh, but the document never shows where it changes data-plane behavior relative to Kong/Pomerium/OpenTelemetry | high |
| Alert schema governance and routing | `platform-alerts` has a minimal schema, but deduplication, inhibition, routing, and escalation rules are not specified | medium |
| Observability ingestion and retention policy | Backends are named, but log shipping, trace ingestion, retention, and storage sizing are not defined | medium |
| SRE dashboard and drilldown contract | Grafana/Kibana workflows are described narratively, but the actual dashboards/links/query conventions are absent | medium |
| Resource quota and cost-control mechanics for dynamic environments | The document says quotas exist but does not define enforcement, defaults, or cost ceilings | high |
| Environment taxonomy beyond `prod`, `stage`, `dev`, and `sue` | Lifecycle models and TTL policy mention multiple environment classes, but the authoritative taxonomy and rules are incomplete | medium |
| Ownership of the scheduled cleanup job | TTL cleanup is required for `sue` environments, but the scheduler runtime and operational owner are unstated | high |
| Static deployment promotion model across environments | The document says promotion is controlled and auditable, but branch/repository/environment mapping is not defined | medium |
| CI/CD credential flow | The pipeline pushes to Harbor and commits to a GitOps repo, but secret/credential acquisition for those actions is unspecified | high |
| Versioning and upgrade policy for platform components | The platform is a dense control-plane stack, but no version pinning or upgrade strategy is provided | medium |
| Backup, restore, and disaster-recovery posture | Core stateful systems like PostgreSQL, Kafka, Harbor, and object storage are central, but resiliency/DR procedures are omitted | high |
| Flink workload applicability | Flink Adaptive Scheduler is selected, but the document never explains which workloads actually require it | high |

## 8. Raw statistics

- Total components mentioned: 57
- Total architectural decisions: 25
- Total implementation units: 33
- Total cross-document dependencies: 14
- Total outdated/questionable flags: 16
