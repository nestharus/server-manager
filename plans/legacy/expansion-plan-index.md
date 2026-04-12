# Expansion Plan Decomposition Index

## 1. Executive summary

This legacy document is a sparse addendum to a broader Vultr/Kubernetes platform blueprint. It introduces six concrete platform additions: Cloudflare at the edge, Trivy for pre-deploy and in-cluster image scanning, Falco for runtime threat detection, Calico for default-deny network policy, Velero for disaster recovery to Vultr object storage, and OpenCost for Kubernetes cost visibility. It also prescribes a rollout method: define per-component configuration and HA details, formalize component contracts, implement in phased layers, validate each new integration, then onboard a pilot application and refine from operational feedback.

The document assumes a substantial platform already exists underneath it: a Vultr-hosted Kubernetes environment, an ingress or traffic-management layer, an observability stack, a CI/CD system, Terraform code, and Kubernetes manifest deployment workflows. The appendix is important: it is not normative architecture on its own, but it captures the research corpus the author used across ingress, GitOps, runtime security, disaster recovery, observability, secrets, and FinOps. Downstream modernization work needs both the explicit additions and the implied inherited platform context.

## 2. Component inventory

Appendix-only comparators and adjacent tools are included here because they are part of the source document's embedded research corpus.

| Component | Role in this spec | Category | External dependency? | Notes |
|---|---|---|---|---|
| Vultr / VKE / Vultr Object Storage | Target cloud, Kubernetes substrate, and backup destination | compute | Yes | Explicit body mention via title and "Vultr S3 bucket"; appendix adds VKE, Flux-on-Vultr, provider-vultr research. |
| Kubernetes | Underlying orchestration platform for every addition | compute | Yes | Title and most appendix URLs assume a Kubernetes environment. |
| Cloudflare / Cloudflare One | Edge perimeter for DNS, WAF, DDoS, and origin-access restriction | networking | Yes | Explicitly selected in body; appendix adds Cloudflare architecture and Cloudflare One/Kubernetes references. |
| DNS | Name resolution at the platform edge | networking | No | Capability named explicitly in the Cloudflare sentence. |
| WAF | Web application firewall at the edge | security | No | Capability named explicitly in the Cloudflare sentence. |
| DDoS protection | Edge anti-abuse and availability protection | security | No | Capability named explicitly in the Cloudflare sentence. |
| Trivy / Trivy Operator | Pre-deploy image scanning and continuous in-cluster scanning | security | Yes | Explicit body addition; appendix references Trivy `v0.37` and `v0.38` docs. |
| Falco | Runtime threat detection from kernel-level syscalls | security | Yes | Explicit body addition; appendix includes Falco source material. |
| Calico | Chosen CNI and policy engine | networking | Yes | Explicit body addition. |
| CNI / Kubernetes NetworkPolicy | Mechanism for default-deny least-privilege networking | networking | No | Explicit via "A CNI" and network-policy research links. |
| Velero / Restic / VolumeSnapshots | Disaster recovery for cluster objects and persistent data | storage | Yes | Explicit body addition plus backup/restore research corpus. |
| OpenCost | Kubernetes cost allocation and FinOps visibility | observability | Yes | Explicit body addition. |
| Kubecost / CloudZero / Apptio | Comparison set informing the OpenCost choice | observability | Yes | Appendix-only cost comparison sources. |
| Prometheus | Metrics source for OpenCost | observability | Yes | Explicit body integration point. |
| Grafana | Visualization layer for OpenCost and Prometheus data | observability | Yes | Explicit body integration point. |
| OTLP | Example inter-component telemetry contract | API | No | Explicit example: applications send data to observability via an OTLP endpoint. |
| Observability component | Existing platform service that receives telemetry | observability | No | Internal platform component assumed, not defined here. |
| Traffic Management component | Existing platform service whose metrics must be observed | networking | No | Internal platform component assumed, not defined here. |
| CI pipeline / CI/CD component | Existing delivery system that hosts scans and deploys manifests | CI/CD | No | Mentioned explicitly but tool choice is unresolved in the body. |
| Terraform | IaC whose repository structure must be standardized | CI/CD | Yes | Explicit body mention plus appendix research. |
| Kong / Kong Gateway / Kong hybrid mode | Ingress and API-gateway research corpus adjacent to the unspecified ingress layer | API | Yes | Appendix only; body does not explicitly re-select Kong. |
| Gateway API | Ingress alternative and comparison topic | API | Yes | Appendix only. |
| HAProxy Ingress | Alternative ingress-controller research topic | networking | Yes | Appendix only. |
| Crossplane / provider-vultr | Provisioning and control-plane research corpus for Vultr clusters | compute | Yes | Appendix only; likely inherited from another legacy spec. |
| FluxCD | GitOps delivery research corpus | CI/CD | Yes | Appendix only; likely inherited from another legacy spec. |
| Ansible | Bootstrap and integration research corpus | CI/CD | Yes | Appendix only. |
| GitLab CI/CD / GitLab Agent | CI orchestration comparator and possible execution substrate | CI/CD | Yes | Appendix only; body says only "CI pipeline." |
| Jenkins | CI/CD comparator | CI/CD | Yes | Appendix only. |
| OpenTelemetry | Observability standard behind the OTLP example and Elastic integrations | observability | Yes | Appendix only; body references OTLP but not OpenTelemetry by name. |
| Elastic / Elasticsearch / Elastic APM | Observability backend research corpus | observability | Yes | Appendix only. |
| Infisical / PKI / k8-kms-plugin | Secrets and KMS research corpus | security | Yes | Appendix only; not explicitly scoped in the body. |
| PostgreSQL | Secret/backend integration research corpus | storage | Yes | Appendix only, via Infisical integration docs. |
| AWS KMS / Kubernetes KMS provider / KMIP | External key-management research corpus | security | Yes | Appendix only. |
| External Secrets Operator | Alternative or adjacent secret-sync mechanism | security | Yes | Appendix only. |
| Amazon EKS | Reference architecture source for Crossplane and Flux patterns | compute | Yes | Appendix only. |
| Google Kubernetes Engine (GKE) | Reference architecture source for networking, Terraform, and Kong patterns | compute | Yes | Appendix only. |
| Rancher Manager | Backup and restore comparison source | compute | Yes | Appendix only. |
| etcd | Control-plane backup topic in recovery research | storage | No | Appendix only. |

## 3. Architectural decisions

1. **Decision**: Place Cloudflare at the platform edge for DNS, WAF, and DDoS protection.
   **Rationale**: "The platform's edge, providing DNS, WAF, and DDoS protection."
   **Scope**: Cloudflare, DNS, WAF, DDoS protection, public ingress path.
   **Confidence**: HIGH
   **Modernization risk**: Yes. Vendor-specific edge assumptions and product boundaries may have changed since the legacy write-up.

2. **Decision**: Restrict the ingress layer to only accept traffic from Cloudflare IP ranges.
   **Rationale**: "The ingress layer will be configured to only accept traffic from Cloudflare's IP ranges to protect the origin."
   **Scope**: Cloudflare, ingress layer, traffic management, origin exposure model.
   **Confidence**: HIGH
   **Modernization risk**: Yes. IP allowlist management is operationally brittle and depends on current Cloudflare-origin integration patterns.

3. **Decision**: Integrate Trivy into the CI pipeline as a pre-deployment security gate.
   **Rationale**: "An image scanner to be integrated into the CI pipeline to block vulnerabilities pre-deployment."
   **Scope**: Trivy, CI pipeline, artifact release policy.
   **Confidence**: HIGH
   **Modernization risk**: Yes. The appendix cites old Trivy versions, so flags, scanners, and severity semantics need current validation.

4. **Decision**: Deploy an in-cluster Trivy operator for continuous scanning of running workloads.
   **Rationale**: "An in-cluster Trivy operator will also be deployed for continuous scanning of running workloads, addressing supply chain security."
   **Scope**: Trivy Operator, Kubernetes workloads, runtime vulnerability reporting.
   **Confidence**: HIGH
   **Modernization risk**: Yes. Operator packaging and CRD behavior may differ in current releases.

5. **Decision**: Add Falco for runtime threat detection based on kernel-level syscalls.
   **Rationale**: "A runtime security tool that detects and alerts on anomalous activity by monitoring kernel-level syscalls."
   **Scope**: Falco, nodes, containers, alerting pipeline.
   **Confidence**: HIGH
   **Modernization risk**: Yes. Falco deployment modes and managed-cluster compatibility have evolved, especially around kernel and eBPF support.

6. **Decision**: Use Calico as the cluster CNI.
   **Rationale**: "A CNI that enables advanced, default-deny network policies."
   **Scope**: Calico, cluster networking, pod connectivity model.
   **Confidence**: HIGH
   **Modernization risk**: Yes. Managed Kubernetes support for alternate CNIs and policy models varies by provider and version.

7. **Decision**: Enforce a least-privilege, default-deny network model to limit lateral movement between pods.
   **Rationale**: "This is crucial for enforcing a least-privilege network model and preventing lateral movement between pods in case of a breach."
   **Scope**: Calico, NetworkPolicy, namespace-to-namespace traffic, service-to-service access.
   **Confidence**: HIGH
   **Modernization risk**: No. The principle is durable even if the exact implementation tool changes.

8. **Decision**: Standardize on Velero for Kubernetes disaster recovery.
   **Rationale**: "The standard for Kubernetes disaster recovery."
   **Scope**: Velero, backup workflows, restore workflows.
   **Confidence**: HIGH
   **Modernization risk**: Yes. The DR principle is sound, but plugin, snapshot, and provider integration details may have changed.

9. **Decision**: Back up cluster resources and persistent volumes to a Vultr S3 bucket.
   **Rationale**: "It will be used to back up and restore cluster resources and persistent volumes to the Vultr S3 bucket, ensuring business continuity."
   **Scope**: Velero, Vultr object storage, persistent volumes, recovery destination.
   **Confidence**: HIGH
   **Modernization risk**: Yes. "Vultr S3 bucket" is legacy wording and needs current product/API verification.

10. **Decision**: Add OpenCost for granular cost allocation and spend visibility.
    **Rationale**: "An open-source tool for granular cost allocation and visibility of Kubernetes resources."
    **Scope**: OpenCost, cost attribution, FinOps workflows.
    **Confidence**: HIGH
    **Modernization risk**: Yes. FinOps tooling, integrations, and data models evolve quickly.

11. **Decision**: Integrate OpenCost with Prometheus and Grafana.
    **Rationale**: "It integrates with Prometheus and Grafana to provide financial insights (FinOps) into cluster spending."
    **Scope**: OpenCost, Prometheus, Grafana, dashboarding.
    **Confidence**: HIGH
    **Modernization risk**: No. The integration pattern is still standard even if setup details differ.

12. **Decision**: Create detailed implementation plans per component before deployment work.
    **Rationale**: "For each tool, research and define its specific implementation details, configuration parameters, and high-availability strategy."
    **Scope**: Cloudflare, Trivy, Falco, Calico, Velero, OpenCost, ownership model.
    **Confidence**: HIGH
    **Modernization risk**: No. This is a process decision rather than a tooling bet.

13. **Decision**: Treat inter-component contracts as first-class artifacts.
    **Rationale**: "Define the 'contracts' between components."
    **Scope**: Observability, traffic management, applications, CI/CD, future platform interfaces.
    **Confidence**: HIGH
    **Modernization risk**: No. The idea is durable and modernization-friendly.

14. **Decision**: Use a defined OTLP endpoint as the application-to-observability contract example.
    **Rationale**: "Such as the OTLP endpoint that applications must use to send data to the Observability component."
    **Scope**: OTLP, application telemetry, observability ingestion.
    **Confidence**: HIGH
    **Modernization risk**: No. OTLP remains the right abstraction even if the backend changes.

15. **Decision**: Implement the added components in a phased, layered approach.
    **Rationale**: "Implement Components in a Phased, Layered Approach."
    **Scope**: Program sequencing, rollout order, change management.
    **Confidence**: MEDIUM
    **Modernization risk**: No. This is a sequencing strategy, not a legacy tool choice.

16. **Decision**: Validate integration and contract conformance after each component is deployed.
    **Rationale**: "As each new component is deployed, test and validate its integration with previously deployed components."
    **Scope**: Deployment verification, integration tests, contract validation.
    **Confidence**: HIGH
    **Modernization risk**: No.

17. **Decision**: Use observability receiving metrics from traffic management as a concrete validation case.
    **Rationale**: "After deploying the Observability component, confirm that it is receiving metrics from the Traffic Management component."
    **Scope**: Observability component, traffic management component, metrics pipeline.
    **Confidence**: MEDIUM
    **Modernization risk**: No. This is an example contract, not a dated tooling choice.

18. **Decision**: Onboard a pilot application only after the core platform components are stable.
    **Rationale**: "Once the core platform components are stable, onboard a pilot application to validate the end-to-end workflow."
    **Scope**: Application onboarding, CI/CD, security scanning, observability, traffic routing.
    **Confidence**: HIGH
    **Modernization risk**: No.

19. **Decision**: Refine the platform based on pilot and operational feedback.
    **Rationale**: "Use feedback from the pilot and ongoing operations to address any implementation gaps and refine the configuration of each component."
    **Scope**: Component tuning, follow-on hardening, backlog generation.
    **Confidence**: HIGH
    **Modernization risk**: No.

20. **Decision**: Standardize the repository structure for Terraform code and Kubernetes manifests managed by the CI/CD component.
    **Rationale**: "Establish a standardized repository structure for managing the Terraform code and the Kubernetes manifests that will be deployed by the CI/CD component."
    **Scope**: Repo layout, Terraform, manifest delivery, CI/CD boundaries.
    **Confidence**: HIGH
    **Modernization risk**: Yes. The desired repo topology may now be owned by newer GitOps or platform conventions in other documents.

## 4. Cross-document dependencies

1. **`platform-v2-core-vke`**
   Components: Vultr, VKE, Kubernetes.
   This document assumes the base cluster and cloud substrate already exist because it only adds perimeter security, runtime security, DR, and FinOps layers on top.
   Likely paired document: [platform-v2.md](/home/nes/discord/plans/legacy/platform-v2.md).

2. **`platform-v2-traffic-mgmt`**
   Components: ingress layer, traffic management component, likely Kong or another ingress/API gateway chosen elsewhere.
   Cloudflare origin protection only makes sense if a concrete ingress stack already exists underneath it.
   Likely paired document: [platform-v2.md](/home/nes/discord/plans/legacy/platform-v2.md).

3. **`platform-v2-observability-base`**
   Components: Observability component, Prometheus, Grafana, OTLP/OpenTelemetry, Elastic backends.
   OpenCost and the explicit OTLP contract both assume a working observability stack already exists.
   Likely paired document: [platform-v2.md](/home/nes/discord/plans/legacy/platform-v2.md).

4. **`gitops-base-delivery`**
   Components: CI pipeline / CI/CD component, manifest deployment path, possibly GitLab CI/CD, FluxCD, Dagger, or adjacent tooling.
   Trivy's pre-deploy gate and the repo-layout requirement both depend on a pre-existing delivery system.
   Likely paired document: [gitops.md](/home/nes/discord/plans/legacy/gitops.md).

5. **`auth-secrets-baseline`**
   Components: Infisical, PKI, KMS integration, secret synchronization.
   Velero, Falco, Trivy Operator, and other additions will need credentials and secret distribution, but this document does not specify that layer itself.
   Likely paired documents: [auth-v5.md](/home/nes/discord/plans/legacy/auth-v5.md) and [platform-v2.md](/home/nes/discord/plans/legacy/platform-v2.md).

6. **Provided capability: `edge-security-baseline`**
   Components: Cloudflare, DNS, WAF, DDoS protection, ingress origin restriction.
   Once implemented, other documents can assume a hardened public edge rather than direct origin exposure.
   Likely downstream consumers: platform ingress docs and any public API/application specs.

7. **Provided capability: `runtime-security-baseline`**
   Components: Trivy, Trivy Operator, Falco, Calico, default-deny network policies.
   Once implemented, CI/CD, application, and auth-related work can assume image scanning, runtime detection, and pod-to-pod isolation as platform guardrails.
   Likely downstream consumers: [gitops.md](/home/nes/discord/plans/legacy/gitops.md), [auth-v5.md](/home/nes/discord/plans/legacy/auth-v5.md), and application-service documents outside this set.

8. **Provided capability: `platform-dr-finops-baseline`**
   Components: Velero, Vultr object storage, OpenCost, Prometheus, Grafana.
   Once implemented, operations documents can assume backup/recovery and cost-visibility capabilities exist, though this document does not define their operating policies.
   Likely downstream consumers: [platform-v2.md](/home/nes/discord/plans/legacy/platform-v2.md) and future operations/runbook documents.

## 5. Implementation units

External unit IDs referenced below:

- `platform-v2-core-vke`: base Vultr/VKE cluster and Kubernetes substrate
- `platform-v2-traffic-mgmt`: existing ingress or API-gateway layer
- `platform-v2-observability-base`: OTLP/OpenTelemetry plus Prometheus/Grafana/Elastic backends
- `gitops-base-delivery`: existing CI/CD and manifest-delivery path
- `auth-secrets-baseline`: existing secret-management and credential-distribution layer

| Unit ID | Title | Description | Dependencies | Components involved | Estimated complexity | Can be parallelized with |
|---|---|---|---|---|---|---|
| `component-contracts` | Define component contracts and HA targets | Produce the missing implementation-facing design layer for the six additions. This includes per-component configuration scope, HA expectations, credential needs, alert destinations, backup destinations, and explicit contracts such as the OTLP ingestion endpoint and validation inputs from traffic management. | `platform-v2-core-vke`, `platform-v2-traffic-mgmt`, `platform-v2-observability-base`, `gitops-base-delivery` | Cloudflare, Trivy, Falco, Calico, Velero, OpenCost, OTLP, Observability component, Traffic Management component, CI/CD component | M | `repo-layout-standardization` |
| `repo-layout-standardization` | Standardize Terraform and manifest repo layout | Establish the canonical repository structure the document calls for, including how Terraform code, Kubernetes manifests, and deployment ownership boundaries are organized for the CI/CD system. This is the storage and workflow contract that subsequent component PRs should target. | `gitops-base-delivery` | Terraform, CI/CD component | M | `component-contracts` |
| `edge-cloudflare-origin-lockdown` | Put Cloudflare in front of the platform and lock down origin access | Configure the edge tier and the origin restriction model so public traffic terminates at Cloudflare and only Cloudflare IP ranges can reach the ingress layer. This unit includes DNS cutover, WAF/DDoS posture, and ingress allowlist enforcement. | `component-contracts`, `platform-v2-core-vke`, `platform-v2-traffic-mgmt` | Cloudflare, DNS, WAF, DDoS protection, Vultr, Kubernetes, Traffic Management component | M | `ci-trivy-predeploy-scan`, `cluster-trivy-continuous-scan`, `runtime-falco-detection`, `dr-velero-vultr-backups`, `finops-opencost-integration` |
| `ci-trivy-predeploy-scan` | Add Trivy as a CI vulnerability gate | Insert image scanning into the pre-deployment pipeline and define what "block vulnerabilities pre-deployment" means in practice. This unit should result in reproducible scan execution and a deterministic pass/fail contract in CI. | `component-contracts`, `repo-layout-standardization`, `gitops-base-delivery` | Trivy, CI pipeline / CI/CD component | S | `edge-cloudflare-origin-lockdown`, `cluster-trivy-continuous-scan`, `runtime-falco-detection`, `dr-velero-vultr-backups`, `finops-opencost-integration` |
| `cluster-trivy-continuous-scan` | Deploy continuous in-cluster image scanning | Install and configure the in-cluster Trivy operator, define what workloads it scans, and expose the resulting findings to the platform's operational surfaces. This is separate from CI scanning because it covers already-running workloads and cluster drift. | `component-contracts`, `platform-v2-core-vke`, `auth-secrets-baseline` | Trivy Operator, Kubernetes, Observability component | M | `edge-cloudflare-origin-lockdown`, `ci-trivy-predeploy-scan`, `runtime-falco-detection`, `dr-velero-vultr-backups`, `finops-opencost-integration` |
| `runtime-falco-detection` | Deploy runtime threat detection | Install Falco and define the detection-to-alert path for anomalous runtime activity. The outcome is a live runtime-security signal that can participate in the platform's broader operational response model. | `component-contracts`, `platform-v2-core-vke`, `platform-v2-observability-base`, `auth-secrets-baseline` | Falco, Kubernetes, Observability component | M | `edge-cloudflare-origin-lockdown`, `ci-trivy-predeploy-scan`, `cluster-trivy-continuous-scan`, `dr-velero-vultr-backups`, `finops-opencost-integration` |
| `network-calico-default-deny` | Install Calico and enforce baseline default-deny policy | Introduce Calico as the networking and policy substrate, then define the minimum viable default-deny policy set that preserves required traffic while blocking lateral movement. This is the riskiest rollout because it can break service connectivity if sequencing is wrong. | `component-contracts`, `platform-v2-core-vke`, `platform-v2-traffic-mgmt` | Calico, CNI / Kubernetes NetworkPolicy, Kubernetes, Traffic Management component | L | `ci-trivy-predeploy-scan`, `cluster-trivy-continuous-scan`, `runtime-falco-detection`, `dr-velero-vultr-backups`, `finops-opencost-integration` |
| `dr-velero-vultr-backups` | Configure Velero backups to Vultr object storage | Deploy Velero, wire it to Vultr object storage, define what gets backed up, and prove restoreability. This unit is only complete when backup and restore are both validated, not merely scheduled. | `component-contracts`, `platform-v2-core-vke`, `auth-secrets-baseline` | Velero, Vultr Object Storage, Restic, VolumeSnapshots, Persistent volumes | M | `edge-cloudflare-origin-lockdown`, `ci-trivy-predeploy-scan`, `cluster-trivy-continuous-scan`, `runtime-falco-detection`, `finops-opencost-integration` |
| `finops-opencost-integration` | Add OpenCost to the observability stack | Deploy OpenCost and integrate it with Prometheus and Grafana so cost data is queryable and visible. This is the smallest self-contained FinOps slice described by the document. | `component-contracts`, `platform-v2-observability-base` | OpenCost, Prometheus, Grafana | S | `edge-cloudflare-origin-lockdown`, `ci-trivy-predeploy-scan`, `cluster-trivy-continuous-scan`, `runtime-falco-detection`, `dr-velero-vultr-backups` |
| `integration-validation-suite` | Validate component integrations and contracts | Build the validation layer the document requires after each deployment. This includes OTLP ingestion checks, traffic-management-to-observability verification, scan-signal verification, backup test verification, and other cross-component contract tests. | `component-contracts`, `edge-cloudflare-origin-lockdown`, `ci-trivy-predeploy-scan`, `cluster-trivy-continuous-scan`, `runtime-falco-detection`, `network-calico-default-deny`, `dr-velero-vultr-backups`, `finops-opencost-integration` | OTLP, Observability component, Traffic Management component, Prometheus, Grafana, CI/CD component | M | None |
| `pilot-application-onboarding` | Onboard a pilot application and close the feedback loop | Deploy a representative application through the hardened platform to validate the end-to-end path from CI/CD to traffic routing, scanning, observability, and cost visibility. Use the results to generate follow-on tuning work, as explicitly required by the document's "Iterate and Refine" step. | `integration-validation-suite` | CI/CD component, Cloudflare, Trivy, Falco, Calico, Velero, OpenCost, Observability component, Traffic Management component | M | None |

## 6. Outdated or questionable elements

1. The appendix cites `doc.crds.dev` pages for `provider-vultr@v0.1.0` and `provider-vultr@v0.2.0`. Those version pins are almost certainly stale by April 2026.
2. The appendix cites Trivy `v0.37` and `v0.38` documentation. Scanner behavior, policy syntax, and operator packaging may differ substantially now.
3. The appendix cites Elastic APM `7.10`, `7.11`, and `7.12` docs. Those are clearly legacy-version references by 2026.
4. "Vultr S3 bucket" is imprecise legacy wording. Modern implementation needs a current check against Vultr Object Storage naming, API behavior, auth model, and Velero plugin support.
5. The appendix researches Kong, HAProxy Ingress, and Gateway API, but the body never resolves which ingress stack the platform actually uses. That leaves a material architectural choice unstated.
6. The appendix researches Crossplane, FluxCD, Ansible, and Terraform, but the body never states which provisioning or reconciliation model this expansion assumes. This likely duplicates ownership from [platform-v2.md](/home/nes/discord/plans/legacy/platform-v2.md).
7. The appendix includes GitLab CI/CD and Jenkins sources, but the body only says "CI pipeline" and "CI/CD component." Execution-engine choice is therefore unresolved here and likely duplicated by [gitops.md](/home/nes/discord/plans/legacy/gitops.md).
8. The appendix includes Infisical, KMS, PKI, and External Secrets material even though the body never introduces a secrets-management change. This is probably duplicated context from [auth-v5.md](/home/nes/discord/plans/legacy/auth-v5.md) and [platform-v2.md](/home/nes/discord/plans/legacy/platform-v2.md).
9. "Develop Detailed Implementation Plans for Each Component" is a future-work placeholder, not an implementable specification. It records intent to defer detail, which downstream planning must now recover.
10. "Onboard Pilot Application" is under-specified. There is no pilot-workload profile, no validation checklist, and no exit criteria.
11. The appendix mixes high-authority sources with volatile ones such as Reddit, Medium, YouTube, Slideshare, StackOverflow, and vendor blogs. Some supporting assumptions are therefore likely low-confidence by 2026.

## 7. Missing elements

1. No explicit HA topology or availability targets are defined for any of the six added components, even though the document says each needs an HA strategy.
2. No failure-mode design is provided for Cloudflare outage, Cloudflare IP-range drift, misconfigured origin allowlists, or direct-origin bypass attempts.
3. No Trivy policy is specified: severity thresholds, false-positive process, waiver model, re-scan cadence, or whether failures block every environment equally.
4. No Falco operating model is specified: rule set, signal-to-alert routing, suppression strategy, escalation path, or incident runbook.
5. No Calico migration plan is specified: current CNI assumptions, namespace bootstrap policies, egress defaults, safe rollout path, or rollback mechanics.
6. No backup policy is specified for Velero: schedules, retention, encryption, RPO/RTO, restore frequency, or what layers of cluster state must be recoverable.
7. No scaling envelope is specified for scans, policy count, backup windows, Falco overhead, or OpenCost metric-cardinality growth.
8. No cost model is provided for the additions themselves: Cloudflare plan costs, object-storage growth, scan compute overhead, runtime-security overhead, or FinOps storage/query retention costs.
9. No monitoring, alerting, or SLO definitions are provided for any added component or for the inter-component contracts the document says to validate.
10. No operational runbooks are defined for IP-range refresh, backup restore, Falco incident response, or network-policy rollback.
11. No pilot-application selection criteria, test matrix, success criteria, or rollback plan are defined.

## 8. Raw statistics

- Total components mentioned: 38
- Total architectural decisions: 20
- Total implementation units: 11
- Total cross-document dependencies: 8
- Total outdated/questionable flags: 11
- Research URLs preserved from the appendix: 95

## 9. Research corpus preserved from the source document

These URLs are preserved because the appendix is part of the legacy document. They are grouped for easier downstream use, but the raw URL strings are kept intact, including duplicates and wrapping parentheses where present in the source.

### 9.1 Ingress, gateway, and edge

`R01` https://konghq.com/blog/engineering/gateway-api-vs-ingress
`R02` https://www.reddit.com/r/devops/comments/14jb0cr/replace_ha_proxy_by_kong/
`R03` https://discuss.konghq.com/t/pros-cons-of-kong-in-hybrid-mode/6968
`R04` https://www.reddit.com/r/kubernetes/comments/pqm6jm/which_ingress_controller_do_you_prefer/
`R21` https://docs.jp.konghq.com/gateway/latest/production/deployment-topologies/hybrid-mode/
`R22` https://developer.konghq.com/gateway/hybrid-mode/
`R23` https://www.slideshare.net/slideshow/flexible-hybrid-apiled-software-architectures-with-kong/238045048
`R24` https://blog.zelarsoft.com/kong-hybrid-mode-deployment-gke-and-on-prem-2b83a5152b6
`R25` https://medium.com/@jamesbordane57/haproxy-ingress-controller-kubernetes-installation-configuration-best-practices-e4f4e225989c
`R26` https://github.com/jcmoraisjr/haproxy-ingress
`R27` https://github.com/haproxytech/kubernetes-ingress
`R28` https://www.haproxy.com/documentation/kubernetes-ingress/overview/
`R50` https://www.cloudflare.com/architecture/
`R51` https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/deployment-guides/kubernetes/
`R52` https://www.reddit.com/r/kubernetes/comments/1cckh21/how_to_expose_services_to_the_internethome_lab/
`R53` https://bobcares.com/blog/cloudflare-kubernetes-load-balancer/
`R77` https://hub.docker.com/r/kong/kong-gateway
`R78` https://developer.konghq.com/gateway/
`R79` https://github.com/Kong/kong
`R80` https://nttdata-dach.github.io/posts/as-kongproductintroduction/
`R81` https://developer.konghq.com/gateway/third-party-support/
`R82` https://stackoverflow.com/questions/71805854/installing-kong-with-postgresql-and-add-service-with-rest-api
`R84` https://mrkaran.dev/posts/setting-up-kong-part-1/
`R85` https://8grams.medium.com/kong-how-to-install-open-source-kong-with-database-on-kubernetes-d0a86d021a29
`R86` ((https://www.youtube.com/watch?v=TG43WxojVrM))
`R87` https://apipark.com/technews/1sK1GFIZ.html
`R88` https://konghq.com/blog/learning-center/api-gateways-for-high-availability-clusters

### 9.2 Provisioning, GitOps, bootstrap, and platform substrate

`R05` https://github.com/aws-samples/eks-gitops-crossplane-flux/blob/main/crossplane.sh
`R06` https://github.com/aws-samples/eks-gitops-crossplane-flux/blob/main/flux.md
`R07` https://medium.com/@mouadeouakil/unleashing-the-power-of-multi-cloud-k8s-clusters-with-crossplane-and-fluxcd-69ea8568c82f
`R08` https://aws.amazon.com/blogs/containers/gitops-model-for-provisioning-and-bootstrapping-amazon-eks-clusters-using-crossplane-and-flux/
`R09` https://spacelift.io/blog/crossplane-vs-terraform
`R10` https://blog.crossplane.io/crossplane-vs-terraform/
`R11` https://medium.com/@bijit211987/crossplane-vs-terraform-which-infrastructure-as-code-tool-is-best-a5f41f65e8a1
`R12` https://zeet.co/blog/crossplane-vs-terraform
`R13` https://github.com/darkwizard242/ansible-role-flux
`R14` https://www.reddit.com/r/devops/comments/1c09ich/what_is_the_point_of_ansible_would_i_benefit_from/
`R15` https://blog.upbound.io/crossplane-ansible-provider
`R16` (https://www.youtube.com/watch?v=TKYSAp2T2Qg)
`R17` https://cloud.google.com/kubernetes-engine/docs/best-practices/networking
`R18` https://www.vultr.com/resources/faq/
`R19` (https://www.youtube.com/watch?v=ZxSDDIJz7BI)
`R20` https://www.vultr.com/kubernetes/
`R29` https://github.com/vultr/crossplane-provider-vultr
`R30` https://github.com/vultr/crossplane-provider-vultr/activity
`R31` https://doc.crds.dev/github.com/crossplane-contrib/provider-vultr@v0.2.0
`R32` https://doc.crds.dev/github.com/crossplane-contrib/provider-vultr@v0.1.0
`R33` https://docs.vultr.com/deploy-applications-using-flux-on-vultr-kubernetes-engine
`R34` https://fluxcd.io/flux/installation/
`R54` https://www.redhat.com/en/blog/ansible-automation-platform-and-hashicorp-terraform-integration-infrastructure-lifecycle-management
`R55` (https://www.reddit.com/r/Terraform/comments/1ajhkeu/terraform_enterprise_with_ansible_automation/)
`R56` https://cloud.google.com/kubernetes-engine/docs/quickstarts/create-cluster-using-terraform
`R57` https://overcast.blog/creating-kubernetes-clusters-with-terraform-in-depth-guide-344e22e7f73e
`R58` https://github.com/vultr/crossplane-provider-vultr
`R59` https://registry.terraform.io/providers/vultr/vultr/latest/docs/resources/instance
`R60` https://spacelift.io/blog/ansible-devops

### 9.3 CI/CD delivery

`R40` https://cpluz.com/blog/kubernetes-ci-cd-automating-deployments-with-jenkins-and-gitlab-ci-cd/
`R41` https://docs.gitlab.com/user/clusters/agent/ci_cd_workflow/

### 9.4 Runtime security and networking

`R35` https://sysdig.com/learn-cloud-native/kubernetes-security-101
`R36` http://trivy.dev/v0.37/tutorials/kubernetes/cluster-scanning/
`R37` http://trivy.dev/v0.38/docs/target/container_image/
`R38` https://github.com/falcosecurity/falco
`R39` https://cloud.ibm.com/docs/containers?topic=containers-network_policies

### 9.5 Backup, recovery, and cost

`R42` https://velero.io/
`R43` ((https://medium.com/@Sh3ban74/simplifying-kubernetes-disaster-recovery-integrating-velero-with-restic-e25f96ca4c5e))
`R44` https://kubernetes.io/docs/concepts/storage/volume-snapshots/
`R45` https://kubernetes.io/docs/tasks/administer-cluster/configure-upgrade-etcd/
`R46` https://ranchermanager.docs.rancher.com/how-to-guides/new-user-guides/backup-restore-and-disaster-recovery/restore-rancher-launched-kubernetes-clusters-from-backup
`R47` https://www.apptio.com/topics/kubernetes/cost-optimization/kubecost-vs-opencost/
`R48` https://www.cloudzero.com/blog/kubecost-vs-opencost/
`R49` ((https://apipark.com/technews/45YeLyo7.html))
`R83` (https://apipark.com/technews/45YeLyo7.html)

### 9.6 Observability

`R61` https://opentelemetry.io/docs/platforms/kubernetes/helm/operator/
`R62` https://opentelemetry.io/docs/platforms/kubernetes/getting-started/
`R63` https://last9.io/blog/opentelemetry-with-grafana/
`R89` https://www.elastic.co/guide/en/apm/get-started/7.12/open-telemetry-elastic.html
`R90` https://www.elastic.co/guide/en/apm/get-started/7.10/open-telemetry-elastic.html
`R91` https://medium.com/@fcakiroglu16/sending-opentelemetry-data-to-elastic-apm-via-the-otel-collector-in-kubernetes-7b5951c9eaca
`R92` https://dev.to/rranjan/opentelemetry-with-elastic-observability-4oik
`R93` https://faun.pub/elastic-apm-and-opentelemetry-integration-49abaaccdad9
`R94` https://www.elastic.co/guide/en/apm/get-started/7.11/open-telemetry-elastic.html
`R95` https://www.elastic.co/docs/solutions/observability/apm/use-opentelemetry-with-apm

### 9.7 Secrets, KMS, and secret synchronization

`R64` https://infisical.com/docs/integrations/app-connections/postgres
`R65` https://infisical.com/docs/documentation/platform/kms/overview
`R66` https://infisical.com/docs/documentation/platform/pki/pki-issuer
`R67` https://infisical.com/docs/api-reference/overview/examples/integration
`R68` https://github.com/Infisical/infisical
`R69` https://infisical.com/docs/documentation/platform/kms-configuration/aws-kms
`R70` https://kubernetes.io/docs/tasks/administer-cluster/kms-provider/
`R71` https://docs.aws.amazon.com/kms/latest/developerguide/keystore-external.html
`R72` https://github.com/Infisical/k8-kms-plugin
`R73` https://infisical.com/docs/internals/security
`R74` https://infisical.com/docs/documentation/platform/kms/kmip
`R75` https://infisical.com/docs/documentation/platform/kms-configuration/overview
`R76` https://external-secrets.io/latest/provider/infisical/
