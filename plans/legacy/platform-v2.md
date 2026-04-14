# Vultr Kubernetes Platform Specification

## Section 1: Platform Goals

This document specifies the architecture and operational model of the Vultr Kubernetes Platform. The platform is designed to achieve a set of primary, non-negotiable objectives across security, developer velocity, and operational efficiency. These goals provide the foundational principles for all subsequent technical specifications.

### 1.1 Security

The platform's security posture is built on a foundation of three non-negotiable, reinforcing principles. These principles represent a fundamental philosophical shift from a model of implicit trust within a secure perimeter to one of explicit, continuous verification for every action, driven by a single source of truth for identity.1
Holistic Security Posture: A single, identity-driven policy and control plane governs all access, from human-to-infrastructure commands to internal service-to-service communication. The objective is to create a state where every action performed on the platform can be definitively correlated to a verified identity.1
Zero Trust Network Access (ZTNA): All access decisions are based on verified identity and context-aware policy, rather than network location. This principle explicitly forbids trust based on network topology, such as being "inside" a particular VPC, and requires that every access request be individually authenticated and authorized.1
Just-in-Time (JIT) Access: Access credentials are granted only at the moment they are needed and are valid only for the minimum duration required to complete a specific task. This approach eliminates long-lived, standing privileges, drastically reducing the security risk posed by credential theft.1

### 1.2 Developer Velocity

The platform is designed to maximize the speed and confidence with which development teams can deliver value.
Declarative Management: The platform must provide a GitOps-driven foundation for all infrastructure and application configuration, enabling declarative management and version-controlled changes.
Dual-Model Environment Management: The platform must support two distinct environment lifecycle models. It will provide rapid, on-demand provisioning and teardown of dynamic development and test environments via a dedicated API. Concurrently, it will maintain a stable, auditable, and strictly controlled promotion path for static production and staging environments through a Git-based workflow.
High-Fidelity Local Development: The platform must deliver a seamless and high-fidelity local-to-production development workflow. This ensures that all continuous integration logic is defined as portable code, identical in local and remote execution environments, thereby eliminating environment drift.

### 1.3 Operational Efficiency

The platform must be built for cost-effective, resilient, and automated operations.
Comprehensive Automation: The platform must achieve end-to-end operational efficiency through declarative automation for both cloud infrastructure and application lifecycles.
Multi-Layered Elasticity: The platform must implement a multi-layered, workload-aware autoscaling strategy. This ensures the platform is both responsive to dynamic load and cost-efficient by precisely matching resources to demand at the node, application, and stateful workload levels.
Proactive AIOps: The platform must establish a proactive, AIOps-driven operational model. This is achieved by centralizing all system alerts onto an event bus and using event-driven automation to trigger automated remediation workflows.
Unified Observability: The platform must provide a unified observability solution where all telemetry signals—metrics, logs, and traces—are enriched with deep, queryable context propagated across the entire request lifecycle.

## Section 2: Technology Stack

The platform is constructed from the following selection of technologies, categorized by their functional domain.

### 2.1 Cloud and Orchestration

Cloud Provider: Vultr
Container Orchestration: Vultr Kubernetes Engine (VKE)

### 2.2 Infrastructure and Configuration

Day 0 Provisioning: Terraform
Day 1+ Provisioning: Crossplane
Initial Installation: Ansible

### 2.3 CI/CD and GitOps

GitOps Engine: FluxCD
CI/CD Engine: Self-Hosted GitLab Runner (Kubernetes Executor)
Local CI Executor: Dagger

### 2.4 Platform Services

Platform API Service: FastAPI
Platform Service Database: PostgreSQL
Change Data Capture (CDC): Debezium

### 2.5 Security and Identity

The platform's security principles are realized through a purpose-built technology stack. Each component has a precisely defined scope and function within the overall architecture.1
Identity Provider: Self-Hosted Authentik. The exclusive single source of truth for all user and service identities, enforcing MFA and acting as the platform's sole OIDC provider.1
Identity-Aware Access Proxy: Pomerium. The gatekeeper for all sensitive infrastructure access (SSH, RDP, DBs) and internal UIs, enabling the ZTNA model for human-to-infrastructure access.1
Real-Time Authorization Engine: OPAL/Cedar. The fine-grained decision engine for application and data-plane authorization, enabling dynamic, Attribute-Based Access Control (ABAC).1
Ephemeral Certificate Authority: Smallstep step-ca. An internal service that mints short-lived, single-use SSH certificates on-demand, enabling the JIT access model.1
Secrets Management: Self-Hosted Infisical. The centralized and exclusive store for all platform secrets, managed via a declarative, GitOps-friendly workflow.1

### 2.6 Storage and Artifacts

Artifact Repository: Self-Hosted Harbor
Production Object Storage: Vultr Object Storage
Local Object Storage: Self-Hosted MinIO

### 2.7 Networking

API Gateway: Kong
Service Mesh: Linkerd

### 2.8 Observability and Automation

Metrics: VictoriaMetrics
Logs and Traces: Elasticsearch & Elastic APM
Event Bus and Alerting: Apache Kafka
Automation Engine: StackStorm

### 2.9 Autoscaling

Node Autoscaling: Karpenter
Application Autoscaling: KEDA
Stateful Workload Scaling: Flink Adaptive Scheduler

## Section 3: Technology and Goal Alignment

This section specifies how the chosen technologies are composed to meet the platform's primary goals. The selection of each tool is purposeful, contributing to a cohesive system that balances security, velocity, and efficiency.

### 3.1 Security Enablement

The platform's security architecture intentionally separates the access paths for public-facing applications and sensitive internal infrastructure, while unifying control through a common identity and policy plane. This creates a multi-layered defense that is both resilient and coherent.1
A core element of the architecture is the Decoupled Trust Model, which uses distinct gateways and credential types for different access domains. Application access is mediated by the Kong API Gateway, which validates JWTs suitable for web sessions. In contrast, all infrastructure access is mediated by Pomerium, which forces a full re-authentication to obtain a separate, extremely short-lived credential (e.g., an SSH certificate) for each connection. This design creates a critical firewall between the two domains; a compromised application JWT is useless for gaining infrastructure access, thus containing the blast radius of a potential breach.1
The Application Access Path: All public-facing API traffic is governed by the Kong API Gateway. Kong intercepts requests, validates the JWT bearer token against Authentik, and upon success, injects standardized identity headers (x-user-id, x-environment-id) before forwarding the request to the target service. This ensures a verified identity is propagated for downstream authorization and observability.1
The Infrastructure Access Path: Access to all sensitive internal resources (e.g., SSH, databases, admin UIs) is governed by Pomerium, which fully implements the ZTNA and JIT principles. Pomerium intercepts all connection attempts and forces a full, interactive OIDC re-authentication with Authentik for every new session. For SSH access, a successful authentication triggers a JIT workflow where Smallstep step-ca mints a single-use, short-lived SSH certificate for that specific session.1
Unified Control Plane: While the access paths are bifurcated, the control plane is unified. OPAL/Cedar serves as the universal, fine-grained authorization engine for application-layer decisions, allowing policies to be managed as code. Infisical acts as the single source of truth for all secrets across the entire platform, providing credentials to all system components through a declarative, auditable workflow.1

### 3.2 Developer Velocity Acceleration

Developer velocity is achieved through tools that automate provisioning, streamline CI/CD, and enable high-fidelity local development.
FastAPI, Debezium, and Apache Kafka form the core of the Platform Service. This service exposes a REST API for developers to request dynamic environments. The asynchronous, event-driven backend, powered by Debezium and Kafka, decouples the API request from the long-running provisioning process, enabling rapid, non-blocking environment creation.
FluxCD and Crossplane power the GitOps workflow for static environments. By continuously reconciling state from a Git repository and object storage, they provide a fully automated, auditable, and controlled promotion path to production.
Dagger unifies the CI/CD pipeline logic. By defining pipelines as code in a general-purpose language, it ensures that the build, test, and publish processes are identical whether run on a developer's laptop or in a GitLab CI job. This eliminates a common source of friction and failure in the development lifecycle.
Kind and MinIO provide the components for a high-fidelity local development environment. Kind simulates the Kubernetes cluster, while MinIO provides an S3-compatible object storage backend, allowing developers to test the full GitOps reconciliation loop on their local machine.1
Harbor acts as the definitive, self-hosted artifact repository. It stores all versioned application container images and OCI-compliant infrastructure artifacts, ensuring that every deployment is repeatable and traceable.1

### 3.3 Operational Efficiency Enhancement

Operational efficiency is driven by a multi-layered automation and observability strategy.
Karpenter provides just-in-time, workload-aware node provisioning. By directly observing pending pods and provisioning optimally-sized nodes, it maximizes resource utilization and minimizes cloud costs compared to traditional cluster autoscaling methods.
KEDA (Kubernetes Event-Driven Autoscaler) enables applications to scale based on external event sources, such as Kafka consumer lag. This allows resource allocation to precisely match application demand and supports scaling to zero replicas during idle periods for significant cost savings.
Flink Adaptive Scheduler delivers granular, intra-job autoscaling for stateful stream processing. It dynamically adjusts the parallelism of specific operators within a Flink job, targeting resources precisely where bottlenecks occur.
VictoriaMetrics, Elasticsearch, and OpenTelemetry constitute the unified observability stack. OpenTelemetry provides the standard for instrumenting applications to emit telemetry that is automatically enriched with critical context. VictoriaMetrics and Elasticsearch provide high-performance backends for storing and querying these metrics, logs, and traces.
Apache Kafka and StackStorm create the AIOps pipeline. Kafka acts as a central, durable alert bus. StackStorm consumes these alerts and executes event-driven automation workflows, enabling automated investigation and remediation of operational issues.

## Section 4: System Integration Points

This section defines the precise handoffs and data flows between technologies during key system processes. The platform's architecture relies on a series of well-defined integrations to achieve its goals of automation and declarative management.

### 4.1 Initial Bootstrap Sequence (IaC Trinity)

The platform is brought into existence through a phased process that transitions from imperative creation to declarative self-management.
Terraform to Vultr: The process begins with a terraform apply command. Terraform communicates with the Vultr API to provision the foundational infrastructure: the management VKE cluster, the dual-VPC DMZ networking, and the Vultr Object Storage bucket that will serve as the source of truth for GitOps.
Terraform to Ansible: Upon completion, Terraform outputs the necessary connection details (e.g., kubeconfig) for the newly created management VKE cluster.1
Ansible to VKE: An Ansible playbook, executing from a bastion host, uses the output from Terraform to connect to the management cluster's API server. It then installs the Helm charts for Crossplane and FluxCD, the core components of the declarative control plane.
FluxCD to Vultr Object Storage: The installed FluxCD instance is configured to monitor a specific path within the Vultr Object Storage bucket created by Terraform. It continuously reconciles the Kubernetes manifests it finds there.
Crossplane to Vultr API: The installed Crossplane instance is configured with Vultr provider credentials. It begins monitoring for its custom resources (like VKECluster claims) and reconciling their state against the Vultr API, taking over all subsequent infrastructure management.

### 4.2 Dynamic Environment Provisioning

The creation of dynamic environments is an asynchronous, event-driven process.
Client to FastAPI: A user or automated tool sends an authenticated HTTP POST request to the /environments endpoint of the Platform Service.
FastAPI to PostgreSQL: The service validates the request against authorization policies and quotas, then inserts a new record representing the desired environment into its PostgreSQL database.
PostgreSQL to Debezium: The Debezium connector, configured to monitor the transaction log (WAL) of the deployments table, captures the INSERT operation as a change data event.
Debezium to Kafka: Debezium serializes this event into a structured JSON message and publishes it to the platform-deployment-requests Kafka topic, ensuring durable persistence of the request.
Kafka to Platform Deployer: The Platform Deployer, a dedicated microservice, is the consumer for this topic. It receives the deployment event message from Kafka.
Platform Deployer to Harbor and Vultr Object Storage: The deployer fetches the required application and infrastructure OCI artifacts from Harbor. It then generates the final JSON claim files for Crossplane and FluxCD and writes them to a designated, environment-specific path in the Vultr Object Storage bucket.
Vultr Object Storage to Crossplane/FluxCD: The respective controllers, monitoring object storage, detect the new claim files and begin the reconciliation process to provision the VKE cluster and deploy the applications.

### 4.3 CI/CD and Static Deployment Pipeline

The static deployment pipeline is a fully automated GitOps flow.
GitLab to GitLab Runner: A git merge to the main branch of an application repository triggers a webhook to GitLab. GitLab CI schedules a job, which is picked up by a self-hosted GitLab Runner pod within the management cluster.
GitLab Runner to Dagger: The CI job's script executes a dagger call command, invoking the Dagger engine to run the pipeline defined in the application's repository.
Dagger to Harbor: The Dagger pipeline builds the application's Docker image and its associated OCI infrastructure artifact. Both are tagged with an immutable identifier (e.g., Git commit SHA) and pushed to the Harbor registry.
Dagger to GitOps Repository: The final stage of the Dagger pipeline checks out a separate GitOps repository, programmatically updates a manifest file (e.g., a Kustomization or HelmRelease) to reference the new artifact tags in Harbor, and commits the change.
GitOps Repository to FluxCD: FluxCD, which is configured to monitor the GitOps repository, detects the new commit and pulls the updated configuration.
FluxCD to VKE Workload Cluster: Flux applies the updated manifest to the target workload cluster's Kubernetes API server.
VKE Workload Cluster to Harbor: The Kubernetes scheduler on the workload cluster initiates a rolling update. The kubelets on the worker nodes pull the newly specified container image from Harbor to deploy the updated application pods.

### 4.4 Centralized Alerting and Automation Pipeline

The operational response system is decoupled and event-driven.
Monitoring Tools to Kafka: Alerting components, such as vmalert from the VictoriaMetrics stack and Elasticsearch Anomaly Detection, are configured as Kafka producers. When an alert fires, they publish a structured JSON message to a central platform-alerts Kafka topic.
Kafka to StackStorm Sensor: A StackStorm sensor is configured as a Kafka consumer subscribed to the platform-alerts topic. It listens for incoming alert messages.
StackStorm Sensor to Trigger: Upon receiving a message, the sensor validates it and fires a corresponding trigger within the StackStorm system. The trigger's payload contains the full data from the alert message.
StackStorm Rule to Action/Workflow: A set of rules within StackStorm matches patterns in the trigger's payload (e.g., alert name, severity, environmentId). A successful match invokes a specific action or a multi-step workflow to perform automated investigation or remediation.

## Section 5: System Contracts

This section formally defines the APIs, data structures, and schemas that govern interactions between system components. These contracts are essential for ensuring interoperability and providing a stable foundation for development and operations.

### 5.1 API Definitions

Platform Service (FastAPI)
Endpoint: POST /environments
Description: Initiates the asynchronous provisioning of a new dynamic environment. The request body must contain service specifications, desired environment type, and other metadata. Access is controlled by Authentik and OPAL/Cedar.
Endpoint: GET /environments
Description: Retrieves a list of dynamic environments that the authenticated user is authorized to view. Provides status and metadata for each environment.
Endpoint: DELETE /environments/{name}
Description: Initiates the asynchronous de-provisioning of a specified dynamic environment. Access is controlled by Authentik and OPAL/Cedar.

### 5.2 Custom Resource Schemas

Crossplane VKECluster (platform.vultr.com/v1alpha1)
Description: A high-level abstraction for declaring a Vultr Kubernetes Engine cluster.
Schema:
spec.parameters.region: A string specifying the Vultr deployment region.
spec.parameters.version: A string specifying the desired Kubernetes version.
spec.parameters.nodePools: An array of node pool objects. Each object contains:
plan: A string specifying the Vultr instance type (e.g., vc2-2c-4gb).
node_quantity: An integer defining the number of nodes in the pool.
auto_scaler: A boolean to enable or disable Vultr's native autoscaler for the pool.
label: A string used as a Kubernetes node label for workload scheduling.
Infisical InfisicalSecret
Description: A custom resource that declaratively requests secrets from the Infisical platform. The Infisical Operator detects this resource, fetches the specified secrets, and materializes them as a native Kubernetes Secret object in the same namespace.
KEDA ScaledObject
Description: A custom resource that defines how a workload (e.g., a Deployment) should be scaled based on external metrics. It links the target workload to one or more triggers and manages the underlying Horizontal Pod Autoscaler (HPA).

### 5.3 Event Data Formats

Deployment Request Event
Topic: platform-deployment-requests
Format: A structured JSON message published by Debezium. The payload contains the complete data from the row inserted into the PostgreSQL deployments table, including fields for user_id, team_id, environment_name, and a JSON object detailing the service specifications.
System Alert Event
Topic: platform-alerts
Format: A structured JSON message with a standardized schema for all alerts. The payload must include fields for alert_name, severity, status (firing/resolved), and a labels object containing all relevant labels from the monitoring system, including environmentId.

### 5.4 Observability Context Propagation Attributes

This contract specifies the set of contextual attributes that must be propagated throughout the request lifecycle and attached to all telemetry signals (logs, metrics, traces) to enable user-centric debugging.
environmentId
Description: The unique identifier for the platform environment.
Source: Extracted from the user's JWT claim by the Kong API Gateway.
Injection Point: Ingress Gateway (as x-environment-id header).
Presence: Must be present in Logs, Metrics, and Traces.
userId
Description: The unique identifier for the authenticated user (sub claim).
Source: Extracted from the user's JWT claim by the Kong API Gateway.
Injection Point: Ingress Gateway (as x-user-id header).
Presence: Must be present in Logs, Metrics, and Traces.
service
Description: The name of the application or microservice processing the request.
Source: Defined as a resource attribute in the OpenTelemetry SDK configuration.
Injection Point: Application Middleware.
Presence: Must be present in Logs, Metrics, and Traces.
route
Description: The API route that matched the incoming request.
Source: Captured by the Kong API Gateway.
Injection Point: Ingress Gateway (as x-route header).
Presence: Must be present in Logs, Metrics, and Traces.
topic
Description: The Kafka topic for messages being produced or consumed.
Source: Captured by the Kafka client's OpenTelemetry instrumentation.
Injection Point: Kafka Producer/Consumer.
Presence: Must be present in Logs, Metrics, and Traces associated with Kafka operations.
query.id
Description: A normalized hash of a SQL query text, used to aggregate metrics without exposing sensitive data.
Source: Generated by the pg_stat_statements PostgreSQL extension.
Injection Point: Metrics Scraper (Prometheus exporter).
Presence: Must be present as a label in PostgreSQL-related Metrics.

## Section 6: Operational Workflows

This section provides step-by-step procedural descriptions for key platform operations. These workflows define the standard operating procedures for developers and operators, ensuring consistency, reliability, and auditability.

### 6.1 Static Environment Deployment Workflow (Git-Managed)

This workflow is mandated for deploying to prod and critical stage environments where stability and auditability are paramount.
Merge Request: A developer finalizes code changes and opens a Merge Request in GitLab against the main branch.
Code Review and Merge: The Merge Request undergoes a mandatory peer review and approval process. Upon approval, the code is merged into the main branch.
CI Pipeline Trigger: The merge event triggers a GitLab CI pipeline defined in the project's .gitlab-ci.yml file.
Artifact Publication: A GitLab Runner executes the pipeline, which invokes a dagger call publish command. The Dagger engine builds immutable, version-tagged Docker and OCI artifacts and pushes them to the Harbor artifact repository.
GitOps Update: The Dagger pipeline's final step programmatically checks out the dedicated GitOps repository, updates the relevant manifest file to point to the new artifact versions in Harbor, and pushes this change to the GitOps repository's main branch.
FluxCD Reconciliation: FluxCD, running in the target workload cluster and monitoring the GitOps repository, detects the new commit. It pulls the updated configuration.
Rolling Deployment: FluxCD applies the updated Kubernetes manifests to the cluster. Kubernetes orchestrates a zero-downtime rolling update, pulling the new container image from Harbor and gradually replacing the old application pods with new ones.

### 6.2 Dynamic Environment Lifecycle Workflow (API-Managed)

This workflow is used for dev and sue (System Under Evaluation) environments that require rapid, on-demand lifecycles.
API Request: A developer, via a CLI or UI, sends an authenticated POST request to the Platform Service API to create a new environment.
Asynchronous Trigger: The Platform Service validates the request and writes a record to its PostgreSQL database. This database write is captured by Debezium, which publishes a durable event to a Kafka topic.
Claim Generation: The Platform Deployer service consumes the event from Kafka. It generates the necessary Crossplane and FluxCD claim files based on the request payload and uploads them to a dedicated path in Vultr Object Storage.
Environment Provisioning: Crossplane and FluxCD, running in the management cluster, detect the new claims and orchestrate the provisioning of the new VKE cluster and the deployment of the specified applications onto it.
Expiration Policy: For sue environments, a default 24-hour expiration policy is enforced. A scheduled cleanup job removes the environment's record from the Platform Service database, which triggers a corresponding teardown event that de-provisions all associated resources.1

### 6.3 High-Fidelity Local End-to-End Testing Workflow

This workflow, orchestrated by Dagger, allows developers to validate changes in a high-fidelity local simulation of the production environment.
Environment Setup: The developer runs dagger call local-env-up. This master function starts a local Kind cluster, deploys lightweight instances of platform services (e.g., Harbor), starts a MinIO container to act as a local S3-compatible object storage, and deploys a local FluxCD instance configured to watch a bucket in MinIO.
Build and Test: The developer makes code changes and runs dagger call test to execute all unit and integration tests within an isolated containerized environment.
Local Publish: Upon successful testing, the developer runs dagger call publish --local. This function builds the production artifacts (Docker image, OCI playbook), pushes them to the local Harbor instance, generates the Kubernetes manifests, and uploads them to the local MinIO bucket.
Local Deployment and Verification: The FluxCD instance in the Kind cluster detects the new manifests in MinIO and applies them, triggering a rolling update of the service. The developer can then interact with the updated service using kubectl to perform end-to-end verification.
Teardown: Once testing is complete, the developer runs dagger call local-env-down, which cleanly destroys the Kind cluster and all associated local containers and resources.1

### 6.4 Multi-Layered Autoscaling Causal Chain

The platform's elasticity is achieved through a cohesive causal chain of autoscalers operating at different layers of the stack. This creates a top-down demand signal and a bottom-up supply response.
Event Surge: A surge in business events causes an external metric, such as Kafka consumer lag, to increase beyond its target threshold.
Application Scaling (KEDA): KEDA, monitoring the Kafka topic, detects the increased lag. It acts as a metrics adapter for the Horizontal Pod Autoscaler (HPA), causing the HPA to scale up the number of replicas for the consumer application's Deployment.
Scheduling Failure: The Kubernetes scheduler attempts to place the new pods, but if there is insufficient CPU or memory capacity on existing nodes, the pods enter a Pending state.
Node Provisioning (Karpenter): Karpenter, the workload-aware node autoscaler, observes the Pending pods. It analyzes their specific resource requests, taints, and tolerations. It then directly calls the Vultr API to provision a new, optimally-sized virtual machine instance that precisely fits the requirements of the pending pods, which are then scheduled onto the new node.

## Section 7: Use Cases

This section provides narrative descriptions of how key platform personas interact with the specified components and workflows to accomplish their tasks.

### 7.1 Use Case: Developer Provisioning a Temporary Test Environment

A developer has just completed a new feature on a branch and needs to conduct end-to-end tests with live dependencies. Using a CLI tool, they execute a command that sends a POST request to the Platform Service API, specifying their feature branch and requesting a sue environment. The request is authenticated by Authentik, and their authorization to create an environment is verified by OPAL/Cedar. The Platform Service initiates the asynchronous deployment via the Kafka-based eventing pipeline. Within minutes, the developer receives a notification with the URL for their new, fully provisioned environment. They conduct their tests, and the platform automatically de-provisions the entire environment 24 hours later due to the sue type's default TTL policy.

### 7.2 Use Case: Operator Deploying a Production Release

An operations team member is tasked with deploying a new critical release to production. The change has already been merged to the main branch following a successful code review. This merge automatically triggered the production deployment pipeline in GitLab CI. The operator monitors the pipeline's progress as Dagger builds the artifacts, pushes them to Harbor, and then commits the version bump to the production GitOps repository. The operator observes in the FluxCD logs as it detects the change and begins the rolling update in the production VKE cluster. The deployment completes with zero downtime, and the entire process, from merge to deployment, is captured in the Git history, providing a complete audit trail.

### 7.3 Use Case: SRE Debugging a Service Performance Degradation

An SRE receives an alert in their designated channel, generated by StackStorm, indicating that the p95 latency for the orders service in the prod environment has breached its SLO. The alert message contains structured data, including the environmentId, service name, and route. The SRE opens the Grafana dashboard linked in the alert and immediately filters by these labels to isolate the relevant metrics. They notice a spike in database query time correlating with the latency increase. Pivoting to Kibana, they filter logs for the same environmentId and service during the incident window. They find several log entries with high duration values, each stamped with a trace_id. Clicking on a trace_id takes them directly to the corresponding distributed trace in Elastic APM. The trace visualization clearly shows a single database span as the source of the latency. The span's attributes include the query.id label. Using this non-sensitive ID, the SRE queries the PostgreSQL performance dashboard in Grafana to view the full execution statistics for that specific query pattern, confirming it as the root cause and providing the development team with a precise target for optimization.
#### Works cited
Auth v5
