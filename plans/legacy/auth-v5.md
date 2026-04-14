# Specification: Unified Identity-Driven Access and Control Plane

This document provides the definitive technical specification for the platform's Authentication (AuthN) and Authorization (AuthZ) subsystem. It is a focused refactoring of the "Auth v4" design proposal.1 It is intended to be the canonical reference for all engineering, operations, and security personnel involved in the implementation, maintenance, and auditing of the platform's access control mechanisms. All components, contracts, and workflows described herein are mandatory unless explicitly stated otherwise. Adherence to this specification is critical for maintaining the platform's security posture.

## Goals

This section defines the three non-negotiable, foundational security principles that serve as the system's primary mandate. These principles are not aspirational; they are the core design drivers from which all subsequent technical decisions are derived.1

### Holistic Security Posture

Definition: Establish a single, identity-driven policy and control plane that governs all access, from human-to-infrastructure commands to internal service-to-service communication.1
Implication: This principle mandates the integration of disparate security functions—authentication, authorization, and audit—into a cohesive ecosystem. The objective is to create a state where every action performed on the platform can be definitively correlated to a verified identity, elevating the platform to a truly secure, end-to-end development and operations environment.1

### Zero Trust Network Access (ZTNA)

Definition: Mandate that all access decisions be based on verified identity and context-aware policy, rather than network location.1
Implication: This principle explicitly forbids trust based on network topology, such as being "inside" a particular VPC. It requires the complete decommissioning of legacy access methods that rely on network perimeter security, including per-VPC VPNs and bastion hosts that use static, long-lived credentials.1

### Just-in-Time (JIT) Access

Definition: Grant access credentials only at the moment they are needed and ensure they are valid only for the minimum duration required to complete a specific task.1
Implication: This principle directly targets the significant security risk posed by credential theft. By eliminating the existence of long-lived, standing privileges—particularly for sensitive infrastructure access—the system drastically reduces the window of opportunity for an attacker to misuse compromised credentials.1
These three goals are not independent but form a reinforcing system. The successful implementation of one principle enables and strengthens the others. For example, when a developer attempts to access a node, the action first falls under the Holistic Security Posture goal, which requires that the attempt be tied to a verifiable identity. This immediately invokes the ZTNA principle, rendering the developer's network location irrelevant and forcing an interaction with an identity-aware gateway. Upon successful authentication, the JIT Access principle is applied, ensuring that instead of using a static key, a new, ephemeral certificate is minted specifically for that session. Thus, a single developer action is governed sequentially by all three principles, demonstrating an integrated security philosophy where each goal is a necessary component of a comprehensive defense strategy.1

## Technology Stack

This section enumerates the primary technology components selected to implement the goals defined in Section 1. Each component has a precisely defined scope and function within the overall architecture.1
Identity Provider: Authentik 1
Identity-Aware Access Proxy: Pomerium 1
Real-Time Authorization Engine: OPAL/Cedar 1
Ephemeral Certificate Authority: Smallstep step-ca 1

## How Tech Stack Solves Goals

This section details how each component of the technology stack directly serves the system's goals. It breaks down each component's functional and architectural purpose and clarifies its position within the design.

### Authentik: The Foundation of Identity

What functional purpose does it fulfill within the design?
Serves as the exclusive and single source of truth for all user and service identities on the platform.1
Manages the complete user lifecycle and enforces authentication policies.1
Enforces mandatory Multi-Factor Authentication (MFA) for all human users, providing a critical defense against credential compromise.1
Acts as the sole OpenID Connect (OIDC) provider, federating identity to all other services requiring authentication.1
Functions as the master authority for user and group membership data, which is consumed programmatically by the authorization engine for dynamic, attribute-based access control decisions.1
What architectural purpose does it fulfill within the design?
Establishes the foundational "Single Source of Identity" principle, ensuring consistency across the platform.1
Provides the verifiable identity claims, delivered via OIDC tokens, upon which all other security components, including Pomerium and OPAL/Cedar, base their access decisions.1
Where does it fit in the design?
Authentik is the foundational layer of the AuthN/AuthZ subsystem. It does not enforce access policies itself but provides the trusted identity primitives—users, groups, and verified sessions—that downstream components rely upon. All authorization policies throughout the platform MUST reference identities that are exclusively managed within Authentik to maintain the integrity of this single source of truth.1

### Pomerium: The Infrastructure Gatekeeper

What functional purpose does it fulfill within the design?
Brokers, authorizes, and audits all non-HTTP sessions, including SSH, RDP, and direct database connections, by leveraging its secure TCP-over-HTTPS tunneling capability.1
Secures web-based access to all internal administrative user interfaces, such as Grafana, Kibana, and Harbor.1
Enforces a full OIDC re-authentication flow with Authentik for every new infrastructure session. This critical function explicitly decouples infrastructure access from any potentially longer-lived application-level JSON Web Tokens (JWTs), mitigating the risk of token theft leading to infrastructure compromise.1
What architectural purpose does it fulfill within the design?
Serves as the primary technical enabler of the Zero Trust Network Access (ZTNA) goal for all human-to-infrastructure access.1
Acts as the Policy Enforcement Point for coarse-grained network access, creating an identity-based perimeter around the platform's sensitive resources.1
Facilitates the complete decommissioning of insecure legacy access methods, such as VPNs and bastion hosts that rely on static SSH keys.1
Where does it fit in the design?
Pomerium sits at the ingress perimeter for all sensitive infrastructure and management plane access. It intercepts connection attempts before they can reach the target resource, forcing a mandatory identity verification against Authentik for every session.1

### OPAL/Cedar: The Fine-Grained Decision Engine

What functional purpose does it fulfill within the design?
Provides fine-grained, Attribute-Based Access Control (ABAC) for both application-layer API requests and internal data-plane operations, such as database queries.1
Makes authorization decisions dynamically at runtime based on declarative Cedar policies that are managed as code.1
Continuously synchronizes user identity attributes from Authentik via OPAL data fetchers. This real-time synchronization ensures that authorization decisions are always based on the most current user status and group memberships.1
What architectural purpose does it fulfill within the design?
Decouples authorization logic from application code. This separation is a significant architectural advantage, allowing security policies to be managed, audited, and updated independently of application development and deployment cycles.1
Provides a flexible and powerful mechanism for enforcing the Principle of Least Privilege at an extremely granular level, moving beyond simple role-based checks to consider a rich set of attributes about the user, resource, and context of a request.1
Where does it fit in the design?
The OPAL/Cedar stack operates within the application and data planes. While Pomerium grants network-level access to a service, OPAL/Cedar determines what specific actions a verified user can perform inside that service, such as read versus write permissions on a specific database table.1

### Smallstep step-ca: The JIT Credential Issuer

What functional purpose does it fulfill within the design?
Mints ephemeral, short-lived SSH certificates on-demand for users immediately following a successful authentication event.1
Configures these certificates with a very short time-to-live (TTL), typically on the order of minutes, which directly ties the credential's validity to the authenticated session.1
What architectural purpose does it fulfill within the design?
Serves as the core technical enabler of the Just-in-Time (JIT) Access goal.1
Eliminates the significant security risks associated with managing, distributing, and rotating static, long-lived SSH keys.1
Enforces the continuous re-validation of a user's access rights at the moment of every new connection attempt, representing a fundamental shift toward a more dynamic and secure access model.1
Where does it fit in the design?
step-ca is an internal service integrated directly into the JIT access workflow. It is invoked by a client-side script after a user authenticates via Pomerium and Authentik, but before the final SSH connection to the target node is established.1
The architecture deliberately establishes a decoupled trust model by employing distinct gateways and credential types for different access domains. Application access is mediated by the Kong API Gateway, which validates potentially longer-lived JWTs suitable for maintaining a user-friendly web session. In stark contrast, infrastructure access is mediated by Pomerium, which forces a full, interactive OIDC re-authentication to obtain a separate, extremely short-lived credential—an SSH certificate—for each new connection. This design is not an incidental detail; it is a foundational security principle that creates a critical firewall between the two domains. If an attacker compromises a web application and exfiltrates a user's JWT, that token is useless for gaining infrastructure access. The compromise is therefore contained, preventing an immediate escalation to a breach of the more sensitive core infrastructure. This layered defense significantly enhances the platform's resilience against common credential-based attacks.1

## Integration Points

The integrity of the AuthN/AuthZ subsystem depends on a set of precisely defined and non-negotiable integration contracts with the broader platform. This section lists the critical integration boundaries that are specified in detail in the following section.1
Identity and Ingress Gateway: The handoff between the public API Gateway (Kong) and the identity provider (Authentik).1
Provisioning and Node Bootstrap: The handoff between the infrastructure provisioner (Crossplane) and the AuthN/AuthZ subsystem to establish trust on newly created nodes.1
Unified Observability: The integration of all AuthN/AuthZ components with the platform's central logging, metrics, and alerting stack.1
Secrets Management: The secure handling of all sensitive credentials required by the AuthN/AuthZ components.1
Application-Layer Authorization: The standard protocol for internal applications to query the central authorization engine (OPAL/Cedar).1

## Contracts

This section provides the precise technical specifications for each integration point. Adherence to these contracts is mandatory for maintaining the system's security, interoperability, and integrity.1

### Contract: Identity and Ingress Gateway

Requirement: Define the interaction at the public application ingress perimeter to ensure a verified identity context is propagated from the edge to internal services.1
Specification:
The Kong API Gateway is the designated primary Ingress Gateway for all public-facing, north-south application API traffic.1
Kong MUST be configured with middleware to perform initial validation of JWTs issued by Authentik for every incoming request that requires authentication.1
Upon successful validation of a JWT, Kong MUST inject a standardized set of context headers into the upstream request. The following headers are mandatory 1:
x-user-id: The value MUST be the unique user identifier sourced from the JWT's sub (subject) claim.
x-environment-id: The value MUST be the unique identifier for the platform environment, sourced from a custom claim within the JWT.
Purpose: This contract is fundamental to the platform's holistic security posture. It ensures that a verified identity and its associated environmental context are securely captured at the edge and propagated deep into the platform for downstream observability and fine-grained authorization decisions.1

### Contract: Provisioning and Node Bootstrap

Requirement: Define the critical handoff between the infrastructure provisioning system and the AuthN/AuthZ subsystem to establish trust from the moment a node is created.1
Specification:
Handoff Protocol: A strict separation of concerns is enforced. Crossplane is solely responsible for provisioning Vultr Kubernetes Engine (VKE) cluster infrastructure. The FluxCD terraform-controller is subsequently responsible for configuring AuthN/AuthZ services on top of that infrastructure once it is reported as ready.1
Contractual Obligation: The Crossplane Composition that defines a VKE cluster MUST include a cloud-init configuration step. This step MUST automatically inject the public key of the central step-ca User CA into the /etc/ssh/sshd_config file (or an equivalent trusted_user_ca_keys file) on every newly provisioned node. This is a non-negotiable requirement.1
Dependency Management: Any Flux Terraform custom resource responsible for configuring AuthN/AuthZ services MUST use FluxCD's dependsOn clause. This clause MUST declare a dependency on the Flux Kustomization resource responsible for deploying prerequisite in-cluster services (e.g., the ingress controller) to prevent race conditions.1
Purpose: The contractual obligation to inject the CA key at boot time is the lynchpin of the JIT SSH access system. It ensures that every node provisioned on the platform is born with implicit trust in certificates issued by step-ca, enabling seamless, secure access without manual key management. Declarative dependency management ensures robust, repeatable environment provisioning.1

### Contract: Unified Observability

Requirement: All AuthN/AuthZ components MUST adhere strictly to the platform's standard observability contracts to enable correlated incident response workflows and a holistic security posture.1
Specification:
Structured Logging Specification:
All AuthN/AuthZ components, specifically including Pomerium and step-ca, MUST emit logs in a structured JSON format to the container stdout for ingestion into the central Elasticsearch cluster.1
Every log entry from every component MUST, where applicable, contain the following fields to ensure consistent correlation 1:
timestamp: String (ISO 8601)
level: String (e.g., "info", "warn", "error")
service.name: String (e.g., "pomerium-proxy", "step-ca")
message: String
userId: String (OIDC sub claim)
environmentId: String (e.g., "prod", "sue-feature-branch")
trace_id: String
pomerium.route: String (Required by Pomerium)
pomerium.decision: String (Required by Pomerium, e.g., "allow", "deny")
stepca.serial: String (Required by step-ca)
stepca.type: String (Required by step-ca, e.g., "ssh", "x509")
Metrics Exposition Specification:
All AuthN/AuthZ components MUST expose operational metrics in the Prometheus exposition format. A dedicated Prometheus exporter MUST be deployed as a sidecar for step-ca.1
Access to /metrics endpoints MUST be secured via Kubernetes NetworkPolicy resources, allowing inbound connections only from vmagent pods within the cluster's private network.1
System Alert Event Specification:
All alerts generated by vmalert based on metrics from any AuthN/AuthZ component MUST be published to the central platform-alerts Kafka topic.1
The Kafka message payload MUST conform to the platform's standard System Alert Event JSON schema, including fields such as alert_name, severity, status, and a labels object containing all relevant telemetry (e.g., service.name, environmentId).1
Purpose: To create a unified, queryable data plane for all security and operational events, allowing SREs and security analysts to correlate user actions with system behavior during an incident.

### Contract: Secrets Management

Requirement: Define the mandatory procedure for managing all sensitive data required by the AuthN/AuthZ subsystem.1
Specification:
All secrets, including Pomerium's OIDC client secret, step-ca private keys, and Terraform provider credentials, MUST be stored and managed exclusively within the central, self-hosted Infisical instance. Hardcoding secrets in Git, configuration files, or container images is strictly forbidden.1
The InfisicalSecret custom resource is the sole declarative mechanism permitted for synchronizing secrets from Infisical into the Kubernetes cluster. The Infisical Operator materializes these as native Kubernetes Secret objects.1
All component deployments MUST be configured to mount these Kubernetes Secret objects. Components MUST NOT access the Infisical API directly from their runtime process.1
Purpose: To enforce a declarative, auditable, and centralized secret management strategy, eliminating secret sprawl and providing a single point of control for rotation and auditing.

### Contract: Application-Layer Authorization

Requirement: Define the standard protocol for any application on the platform to query the OPAL/Cedar engine for fine-grained authorization decisions.1
Specification:
Enforcement Point: Applications requiring fine-grained, real-time authorization MUST be instrumented to act as a Policy Enforcement Point (PEP).1
Protocol: Before executing a protected operation, the application MUST make a synchronous HTTP POST request to its local Cedar agent's /is_authorized endpoint.1
Request/Response: The request body MUST be a JSON object conforming to the Cedar Authorization Query format. The application is responsible for parsing the Allow or Deny decision from the agent's JSON response and enforcing it. The outcome MUST be logged.1
API Specification:
Endpoint: POST /is_authorized
Request Body (JSON Schema):
principal: Type: String, Required: Yes. The entity requesting access, in Cedar entity format. Example: "User::\"alice@example.com\""
action: Type: String, Required: Yes. The action being attempted, in Cedar entity format. Example: "SQL::Action::\"insert\""
resource: Type: String, Required: Yes. The resource being accessed, in Cedar entity format. Example: "Table::\"prod.invoices\""
context: Type: Object, Required: No. A JSON object of additional contextual attributes.
Success Response Body (200 OK, JSON Schema):
decision: Type: String, Required: Yes. The authorization decision. MUST be either "Allow" or "Deny".
diagnostics: Type: Object, Required: Yes. An object containing the set of policies that led to the decision and any errors encountered.
Purpose: To extend the central policy engine's control into the application data plane, allowing complex, business-logic-driven authorization to be managed as policy-as-code, consistent with the rest of the platform's security model.

## Workflows

This section details the standard operating procedures for platform teams interacting with the AuthN/AuthZ control plane. These workflows are the practical embodiment of the system's declarative and contract-driven design. The successful execution of these workflows is entirely dependent on the strict enforcement of the integration contracts.

### Operator Workflow: GitOps-Driven Access Policy Administration

Scenario: An operator needs to grant the db-admins group, managed in Authentik, access to a new production database brokered by Pomerium.1
Steps:
The operator creates a new feature branch in the central GitOps monorepo.1
The operator navigates to the infrastructure/terraform/auth-plane/ directory and modifies the relevant .tf file, adding a new pomerium_policy resource that links the db-admins group to the database route.1
The operator commits the change and opens a pull request against the main branch.1
The CI pipeline automatically triggers. As mandated by the Declarative Policy Management Contract, it runs terraform plan and posts the formatted output as a comment in the pull request, providing reviewers with a clear summary of the proposed policy change.1
Team members review the proposed policy change directly in the code and verify the expected outcome from the plan output. Once approved, the pull request is merged.1
FluxCD's terraform-controller, monitoring the main branch, detects the change and automatically initiates its reconciliation loop, executing terraform apply.1
The controller uses its configured credentials to communicate with Pomerium's API, creating or updating the policy. The new access rule is live within minutes of the merge.1
Outcome: A critical access policy change is made declaratively, subjected to mandatory peer review, validated by CI, and deployed automatically. The entire lifecycle of the change is captured in the Git history, providing a complete and immutable audit trail.1

### SRE Workflow: Correlated Incident Response

Scenario: An SRE receives a high-priority latency alert for the orders service in the production environment.1
Steps:
The SRE receives a contextualized alert from StackStorm, delivered via a Kafka message that conforms to the System Alert Event Specification. The alert payload contains structured labels: alert_name="HighLatency", service="orders", environmentId="prod".1
Correlation Point 1 (Human Access Investigation): The SRE queries Kibana, filtering on Pomerium logs from the incident's timeframe. They use the labels from the alert to construct a precise query: service.name: "pomerium-proxy" AND pomerium.route: "prod-orders-db". This immediately reveals if any users were connected to the service's database during the incident, along with their userId, sourced from the structured logs.1
Correlation Point 2 (Metrics and Traces): The SRE pivots to Grafana, using the same labels to view metrics for the orders service, and observes a spike in database query time. Back in Kibana, they find application logs for the orders service that also contain the userId and a trace_id.1
Correlation Point 3 (Root Cause Analysis): The SRE clicks the trace_id in the log entry, which opens the full distributed trace in Elastic APM. The trace visualization clearly pinpoints a specific, slow database span as the root cause of the overall request latency.1
Outcome: The SRE has constructed a complete, correlated view of the incident, moving seamlessly from a system-level alert to identifying potential human interaction, to application logs, and finally to a specific trace identifying the root cause. This powerful capability is a direct result of the strict enforcement of the observability contracts; a single component failing to propagate the userId or trace_id would break this entire analytical chain.1
The operational viability of these workflows serves as a practical validation of the system's architecture. The SRE workflow, for instance, is not merely a procedure but an end-to-end test of the integration strategy. It begins with an alert conforming to the System Alert Event contract. The first query relies on Pomerium adhering to the Structured Logging contract. The pivot to application logs depends on both the application's adherence to the same logging contract and the initial identity propagation from the Ingress Gateway contract. A failure by any single component to meet its contractual obligation would sever the analytical chain, rendering rapid, correlated root cause analysis impossible. This demonstrates that the "Holistic Security Posture" is not just an abstract goal but an operational reality achieved through disciplined, contract-driven integration.1

## Use-Cases

This section describes key end-to-end user journeys, illustrating how the system provides secure and usable access to different personas.

### Developer Use-Case: Just-in-Time Infrastructure Access

Scenario: A developer needs ephemeral shell access to a node in a dynamic test environment to debug an issue.1
Steps:
The developer executes a standard SSH command from their local terminal: ssh <user>@<node-ip-from-sue-env>.1
A ProxyCommand configured in the developer's local SSH configuration intercepts this command and executes a dedicated, platform-maintained access-wrapper script.1
The script invokes the pomerium-cli tool, which automatically opens the system's default web browser and directs the developer to Authentik for a full OIDC login, including a mandatory MFA challenge.1
Upon successful authentication, Authentik returns an OIDC ID token to the CLI tool.1
The script then calls step ssh certificate, passing the OIDC ID token to the internal step-ca service.1
step-ca validates the token with Authentik's public keys and, upon success, issues a new SSH certificate with a very short validity (e.g., 5 minutes).1
The step-cli tool automatically loads the newly minted certificate and its corresponding private key into the developer's running SSH agent.1
Simultaneously, the pomerium-cli process establishes a secure TCP-over-HTTPS tunnel to the target node's SSH port, brokered by the Pomerium proxy.1
The developer's original SSH client proceeds through the established tunnel and presents the new certificate to the node's sshd daemon.1
The sshd daemon validates the certificate against its trusted CA public key—injected at boot time per the Provisioning and Node Bootstrap Contract—and grants access.1
Outcome: The developer gains seamless, audited, and ephemeral shell access. The entire multi-step authentication and cryptographic process is orchestrated automatically after the initial SSH command, providing a superior user experience while enforcing a stringent JIT security model.1

### Security Protocol: Emergency "Break-Glass" Access

Scenario: A catastrophic, system-wide failure of the primary authentication systems occurs, rendering both Authentik and Pomerium unavailable.1
Mechanism: This protocol intentionally and completely bypasses the entire AuthN/AuthZ stack described in this document. It relies on a maximum of three dedicated, non-federated user accounts with Administrator roles created directly in the Vultr Customer Portal.1
Procedure:
Credential Management: The credentials for each account consist of a long, randomly generated password and an associated physical hardware MFA token (e.g., YubiKey). The password (printed) and the token are sealed together in a numbered, tamper-evident envelope. These envelopes are stored in physically secure, geographically distributed safes.1
Access Protocol: Accessing a safe to retrieve an envelope requires documented, logged approval from two individuals from separate leadership chains (e.g., one from Engineering, one from Security/Compliance).1
Incident Declaration: Any use of a break-glass account is automatically classified as a Severity 1 security incident. This triggers immediate, high-priority alerts to platform leadership, automated by ingesting Vultr audit logs into the platform's alerting pipeline.1
Post-Use Mandates: The protocol MUST be tested on a quarterly basis. Following any use (test or real emergency), the protocol mandates immediate password rotation for the used account, revocation of all active sessions, and a full, formal audit of all actions performed during the session.1
Outcome: A secure, audited, and high-friction last-resort access method exists for true emergencies. Its design discourages casual use and ensures that any activation is a highly visible and scrutinized event, demonstrating a mature risk management posture.1
