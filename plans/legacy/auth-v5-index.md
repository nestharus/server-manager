# Structured Decomposition: auth-v5

## 1. Executive summary

This document specifies the platform's unified authentication and authorization control plane. Its scope covers human identity, infrastructure access, application-layer authorization, node bootstrap trust, observability contracts, secret handling, GitOps policy administration, developer JIT SSH access, and emergency break-glass access. It assumes a larger platform already exists underneath it: Kubernetes on Vultr VKE, Kong at public ingress, Crossplane plus Flux for provisioning and reconciliation, Elasticsearch/Prometheus/Kafka/Elastic APM for observability, Infisical for secrets, and a GitOps monorepo with CI. The spec's central model is: Authentik is the sole identity source, Pomerium is the infrastructure gatekeeper, OPAL/Cedar is the fine-grained decision engine, and step-ca issues short-lived SSH credentials. The document is strong on integration contracts and intended workflows, but it leaves migration, high availability, recovery, scaling, and cost modeling mostly unspecified.

## 2. Component inventory

| Component | Role in this spec | Category | External dependency? | Notes |
|---|---|---|---|---|
| Authentik | Sole identity provider and source of truth for users, groups, sessions, and OIDC federation | auth | Yes | Mandatory foundation for every downstream access decision |
| Pomerium | Identity-aware access proxy for infra, admin UIs, and tunneled non-HTTP sessions | networking | Yes | Also functions as coarse-grained policy enforcement point |
| Pomerium API | Control-plane API used by Terraform/Flux to create or update access policies | API | Yes | Explicitly called by the GitOps reconciliation workflow |
| OPAL | Real-time policy/data distribution layer for authorization decisions | auth | Yes | Pulls identity attributes from Authentik into the policy plane |
| Cedar | Policy language and decision engine for fine-grained authorization | auth | Yes | Used for application-layer and data-plane decisions |
| Smallstep step-ca | Ephemeral certificate authority for JIT SSH access | security | Yes | Issues short-lived SSH certificates after successful auth |
| Kong API Gateway | Public north-south ingress gateway for application traffic | API | Yes | Validates Authentik JWTs and injects identity context headers |
| Kubernetes | Runtime environment assumed by secrets, sidecars, NetworkPolicies, and controllers | compute | Yes | Not specified here, but required by most contracts |
| Vultr Kubernetes Engine (VKE) | Managed Kubernetes substrate for provisioned clusters/nodes | compute | Yes | Provisioned by Crossplane according to the bootstrap contract |
| Crossplane | Infrastructure provisioner for VKE clusters | CI/CD | Yes | Explicitly limited to infra provisioning, not auth-plane configuration |
| Crossplane Composition | Declarative definition for VKE cluster provisioning | CI/CD | No | Must embed the CA trust bootstrap step |
| FluxCD terraform-controller | Reconciles Terraform-based auth-plane configuration | CI/CD | Yes | Runs after infrastructure is reported ready |
| Flux Terraform custom resource | Declarative unit that triggers Terraform reconciliation | CI/CD | No | Must use `dependsOn` for prerequisite ordering |
| Flux Kustomization | Dependency anchor for prerequisite in-cluster services | CI/CD | No | Referenced by the bootstrap ordering contract |
| Terraform | Policy/configuration mechanism for Pomerium and related auth-plane resources | CI/CD | Yes | Used in the GitOps workflow via `plan` and `apply` |
| GitOps monorepo | Source of truth for declarative auth policy changes | CI/CD | Yes | Operators modify Terraform here and open PRs |
| CI pipeline | Validates policy changes before merge | CI/CD | Yes | Must run `terraform plan` and surface formatted output in PRs |
| Infisical | Central self-hosted secret manager | security | Yes | Exclusive secret authority for the subsystem |
| InfisicalSecret | Declarative sync mechanism from Infisical into Kubernetes | security | No | Only allowed sync path into the cluster |
| Infisical Operator | Materializes synced values as Kubernetes Secrets | security | Yes | Runtime components depend on it indirectly |
| Kubernetes Secret | Runtime secret delivery mechanism for auth components | security | No | Components mount these instead of calling Infisical directly |
| Infisical API | Secret manager API intentionally blocked from runtime processes | API | Yes | Explicitly disallowed for direct access by deployed components |
| Elasticsearch | Central log storage for structured auth logs | observability | Yes | Ingests JSON logs from auth components |
| Grafana | Example internal administrative UI secured by Pomerium | observability | Yes | Also used by SREs in the correlated incident workflow |
| Kibana | Example internal administrative UI and log investigation surface | observability | Yes | Queried for Pomerium and application logs during incidents |
| Elastic APM | Distributed tracing backend used in incident RCA workflow | observability | Yes | Final pivot point in the SRE workflow |
| Prometheus exposition format | Required metrics output format for auth components | observability | No | step-ca needs extra exporter coverage |
| Prometheus exporter | Dedicated metrics adapter for step-ca | observability | No | Required as a sidecar deployment |
| vmagent | Only allowed Prometheus-scraping client for `/metrics` endpoints | observability | Yes | NetworkPolicy must restrict access to these pods |
| vmalert | Generates auth-related alerts from metrics | observability | Yes | Publishes to Kafka |
| Kafka | Central alert/event bus | messaging | Yes | Carries `platform-alerts` messages and StackStorm inputs |
| StackStorm | Receives/forwards contextualized alerts for operators/SREs | messaging | Yes | Entry point in the SRE incident workflow |
| Harbor | Example internal administrative UI protected by Pomerium | other | Yes | Mentioned as a web UI to secure behind the auth plane |
| ingress controller | Prerequisite in-cluster service for auth-plane reconciliation ordering | networking | Yes | Flux dependencies must wait for it |
| cloud-init | Node bootstrap mechanism for SSH CA trust injection | compute | No | Must install step-ca User CA trust at birth |
| Multi-Factor Authentication (MFA) | Mandatory second factor for all human authentication | auth | No | Required at least in Authentik and in break-glass access |
| OpenID Connect (OIDC) | Federation protocol between Authentik and downstream components | auth | No | Used for both app access and infra re-authentication |
| JSON Web Token (JWT) | Application-session token validated at Kong | auth | No | Explicitly not sufficient for infra access |
| Attribute-Based Access Control (ABAC) | Authorization model implemented by OPAL/Cedar | auth | No | Used for application and data-plane decisions |
| Policy Enforcement Point (PEP) | Role applications must implement to call Cedar | auth | No | Every protected app becomes an enforcement point |
| Cedar agent | Local authorization endpoint queried synchronously by apps | auth | No | Hosts `/is_authorized` |
| Cedar Authorization Query format | Request contract for authorization checks | API | No | Contains principal, action, resource, and optional context |
| HTTP | Transport used by applications to query Cedar | API | No | Specifically synchronous `POST` requests |
| SSH | Primary infrastructure access protocol for developers/operators | networking | No | Moved from static keys to short-lived certificates |
| SSH certificate | Short-lived credential issued by step-ca | security | No | Minutes-scale TTL is central to JIT access |
| sshd | Node-side verifier of SSH certificates | security | No | Trusts the injected step-ca User CA key |
| SSH agent | Client-side key/certificate holder used during JIT access | security | No | Populated automatically by `step-cli` |
| RDP | Non-HTTP session type brokered by Pomerium | networking | No | Mentioned as part of the infra access surface |
| TCP-over-HTTPS tunneling | Pomerium transport for non-HTTP sessions | networking | No | Used to reach SSH/RDP/database endpoints |
| ProxyCommand | SSH interception hook that triggers the JIT access wrapper | other | No | Lives in local SSH client config |
| access-wrapper script | Local client-side orchestration script for JIT SSH | other | No | Invokes Pomerium and step tooling in sequence |
| pomerium-cli | Client CLI that launches browser auth and establishes tunnels | other | Yes | Required on developer workstations |
| step-cli | Client CLI that requests and loads SSH certificates | other | Yes | Executes `step ssh certificate` and updates SSH agent |
| `step ssh certificate` | Concrete client command used to mint SSH certificates | other | No | Invoked after successful OIDC login |
| web browser | Interactive auth surface opened by `pomerium-cli` | other | Yes | Required for full OIDC + MFA login flow |
| Vultr Customer Portal | Break-glass access surface for emergency admin accounts | other | Yes | Completely bypasses the normal auth stack |
| YubiKey | Example hardware MFA token for break-glass accounts | security | Yes | Stored with printed passwords in tamper-evident envelopes |
| Vultr audit logs | Audit source for detecting break-glass usage | observability | Yes | Must feed the alerting pipeline |
| VPC | Legacy network-perimeter trust model explicitly rejected | networking | Yes | Mentioned only as something not to trust |
| VPN | Legacy access path to be decommissioned | networking | Yes | Specifically per-VPC VPNs are forbidden as a trust model |
| bastion hosts | Legacy infrastructure access mechanism to remove | compute | Yes | Rejected because they depend on static credentials |
| static SSH keys | Legacy standing credential model to eliminate | security | No | Replaced by short-lived SSH certificates |

## 3. Architectural decisions

| ID | Decision | Rationale | Scope | Confidence | Modernization risk |
|---|---|---|---|---|---|
| AD-01 | Use a single identity-driven policy and control plane for all access domains | "single, identity-driven policy and control plane" governs human and service access | Entire auth plane, infra access, app access, audit | HIGH | Low; principle-level decision |
| AD-02 | Correlate every platform action to a verified identity | "every action performed on the platform can be definitively correlated to a verified identity" | Authentik, Kong, Pomerium, OPAL/Cedar, logs, traces | HIGH | Low; stable security principle |
| AD-03 | Base access decisions on identity and context, not network location | ZTNA "forbids trust based on network topology" | Kong, Pomerium, node access, service access | HIGH | Low; principle-level |
| AD-04 | Remove legacy perimeter-based access methods | Explicit call to decommission "per-VPC VPNs and bastion hosts" using long-lived credentials | VPNs, bastions, static SSH keys, operator workflows | HIGH | Medium; migration may collide with current ops reality |
| AD-05 | Enforce JIT access instead of standing privileged credentials | Access credentials should exist only "for the minimum duration required" | step-ca, SSH, infra access, client tooling | HIGH | Low; principle-level |
| AD-06 | Standardize on Authentik as the exclusive identity source of truth | Authentik "serves as the exclusive and single source of truth" | User lifecycle, groups, OIDC, downstream services | HIGH | Medium; product capability/upgrade drift must be checked |
| AD-07 | Require MFA for every human user | Authentik "enforces mandatory Multi-Factor Authentication (MFA) for all human users" | Authentik, user login, break-glass expectations | HIGH | Low; stable requirement |
| AD-08 | Use Authentik as the sole OIDC provider for the platform | Authentik "acts as the sole OpenID Connect (OIDC) provider" | Kong, Pomerium, step-ca token validation, apps | HIGH | Medium; IdP integration details may drift across versions |
| AD-09 | Require all authorization policies to reference Authentik-managed identities only | Policies "MUST reference identities that are exclusively managed within Authentik" | Cedar policies, Pomerium policies, app authorization | HIGH | Low; stable model, but migration from other identity sources could be hard |
| AD-10 | Use Pomerium as the gatekeeper for infrastructure and admin UI access | Pomerium "brokers, authorizes, and audits" non-HTTP sessions and secures internal UIs | SSH/RDP/DB access, Grafana/Kibana/Harbor | HIGH | Medium; product and deployment model should be revalidated |
| AD-11 | Force a full OIDC re-authentication for every new infrastructure session | Pomerium "enforces a full OIDC re-authentication flow ... for every new infrastructure session" | Pomerium, Authentik, workstation UX, infra access | HIGH | Medium; strong UX/security tradeoff may need rechecking |
| AD-12 | Separate app access credentials from infrastructure access credentials | Kong handles app JWTs, while Pomerium requires fresh OIDC and SSH certs; stolen JWTs must be "useless for gaining infrastructure access" | Kong, JWT lifecycle, Pomerium, step-ca | HIGH | Medium; exact token/session boundaries can drift with product capabilities |
| AD-13 | Use OPAL/Cedar as the central fine-grained authorization engine | Selected stack item: "Real-Time Authorization Engine: OPAL/Cedar" | Application APIs, data-plane access, policy management | HIGH | Medium; Cedar adoption and OPAL integrations require validation |
| AD-14 | Manage authorization as policy-as-code outside application code | Auth logic is "decoupled from application code" and Cedar policies are "managed as code" | App services, policy repo/process, audits | HIGH | Low; stable architectural pattern |
| AD-15 | Continuously synchronize identity attributes from Authentik into OPAL/Cedar | Authorization must be based on "the most current user status and group memberships" | Authentik, OPAL fetchers, Cedar decisions | HIGH | Medium; fetcher interfaces and sync semantics may change |
| AD-16 | Use step-ca as the JIT issuer for SSH credentials | step-ca is the "core technical enabler" of JIT access | step-ca, SSH workflows, node trust | HIGH | Medium; CA tooling/version compatibility needs validation |
| AD-17 | Keep SSH certificates very short-lived, on the order of minutes | Certificates use "a very short time-to-live (TTL), typically on the order of minutes" | step-ca, client tooling, operator/developer workflows | HIGH | Medium; TTL values and renewal behavior are unspecified |
| AD-18 | Invoke step-ca from a client-side workflow after auth but before final SSH | step-ca "is invoked by a client-side script" after Pomerium/AuthN and before SSH | access-wrapper script, step-cli, pomerium-cli, workstations | HIGH | Medium; workstation tooling and command contracts may drift |
| AD-19 | Treat Kong as the primary public ingress gateway for authenticated APIs | "The Kong API Gateway is the designated primary Ingress Gateway" | Public API ingress, JWT validation, downstream apps | HIGH | Medium; gateway choice may overlap with platform-wide ingress evolution |
| AD-20 | Propagate verified identity context from Kong via standard headers | Kong must inject `x-user-id` from JWT `sub` and `x-environment-id` from a custom JWT claim after validation | Kong, upstream services, logs, Cedar callers | HIGH | Medium; header names and trust model must align with platform-wide conventions |
| AD-21 | Split infra provisioning and auth-plane configuration between Crossplane and Flux | "Crossplane is solely responsible" for VKE infra; Flux terraform-controller configures auth services afterward | Crossplane, Flux, VKE, auth deployments | HIGH | Medium; controller ecosystem and ownership split may change |
| AD-22 | Inject the step-ca User CA trust anchor during node bootstrap | Crossplane Composition "MUST include a cloud-init configuration step" that adds the CA key | Crossplane, cloud-init, sshd, nodes, step-ca | HIGH | Medium; boot-time-only trust injection may be insufficient for rotation |
| AD-23 | Use declarative dependency ordering to avoid auth-plane race conditions | Flux Terraform CRs "MUST use FluxCD's dependsOn clause" | Flux Terraform CRs, Flux Kustomizations, ingress controller | HIGH | Medium; terraform-controller behavior and Flux APIs may drift |
| AD-24 | Standardize auth-component logs as structured JSON to stdout with common fields | Components "MUST emit logs in a structured JSON format to the container stdout"; required fields include `timestamp`, `level`, `service.name`, `message`, `userId`, `environmentId`, `trace_id`, plus `pomerium.route`, `pomerium.decision`, `stepca.serial`, and `stepca.type` where applicable | Pomerium, step-ca, apps, Elasticsearch, Kibana | HIGH | Medium; logging field set may duplicate broader platform standards |
| AD-25 | Expose Prometheus-format metrics from every auth component and add a step-ca sidecar exporter | "All AuthN/AuthZ components MUST expose operational metrics" and step-ca needs a dedicated exporter | Pomerium, step-ca, Prometheus scraping | HIGH | Medium; exporter availability and metric naming require verification |
| AD-26 | Restrict `/metrics` access to vmagent through Kubernetes NetworkPolicies | `/metrics` endpoints MUST allow inbound traffic "only from vmagent pods" | Kubernetes, vmagent, NetworkPolicies, auth services | HIGH | Low; concrete but stable policy pattern |
| AD-27 | Publish auth-generated alerts to Kafka using the standard System Alert Event schema | Alerts "MUST be published to the central platform-alerts Kafka topic"; payloads must include `alert_name`, `severity`, `status`, and contextual labels such as `service.name` and `environmentId` | vmalert, Kafka, StackStorm, incident response | HIGH | Medium; topic/schema ownership likely lives outside this document |
| AD-28 | Centralize all secrets in Infisical and sync them declaratively into Kubernetes | Secrets "MUST be stored and managed exclusively" in Infisical and synced via InfisicalSecret/Operator | Infisical, operator, Kubernetes Secrets, deployments | HIGH | Medium; product/operator details may change |
| AD-29 | Forbid deployed components from calling Infisical directly at runtime | Components "MUST NOT access the Infisical API directly from their runtime process" | Runtime pods, secret delivery, network/security policy | HIGH | Low; stable design constraint |
| AD-30 | Require applications needing fine-grained auth to act as PEPs and call a local Cedar agent synchronously | Apps "MUST be instrumented" and "MUST make a synchronous HTTP POST request" before protected operations; requests carry `principal`, `action`, `resource`, optional `context`, responses return `decision` (`Allow` or `Deny`) and `diagnostics`, and the outcome must be logged | Application services, Cedar agents, logging | HIGH | Medium; synchronous local-agent model may need latency/availability review |
| AD-31 | Manage Pomerium access policy changes through GitOps and Terraform | Workflow uses feature-branch edits under `infrastructure/terraform/auth-plane/`, adds `pomerium_policy` resources, requires PR review, runs CI `terraform plan` with formatted PR comments, and applies through Flux against the Pomerium API | GitOps repo, CI, Terraform, Flux, Pomerium, Pomerium API | HIGH | Medium; controller/resource contracts may drift |
| AD-32 | Treat correlated incident response as a first-class architecture requirement | The workflow depends on alerts, Pomerium logs, app logs, and traces sharing labels such as `userId` and `trace_id`; the example chain starts from a `HighLatency` alert on `orders` in `prod`, pivots through `service.name: "pomerium-proxy" AND pomerium.route: "prod-orders-db"`, and ends at a slow database span in Elastic APM | StackStorm, Kafka, Kibana, Grafana, Elastic APM, application logging | HIGH | Medium; depends on multiple external stacks staying aligned |
| AD-33 | Implement JIT SSH access through a local CLI chain rooted in the user's `ssh` command | The use-case defines `ssh` -> `ProxyCommand` -> wrapper -> `pomerium-cli` -> browser/OIDC -> `step ssh certificate` -> tunnel -> `sshd` | Developer workstations, step-cli, pomerium-cli, Pomerium, step-ca, sshd | HIGH | Medium; CLI UX and command interfaces may change |
| AD-34 | Preserve an explicit break-glass path outside the main auth plane | Protocol "intentionally and completely bypasses the entire AuthN/AuthZ stack" using up to three non-federated Vultr portal admins with printed passwords plus hardware MFA in numbered tamper-evident envelopes, two-person approval, automatic Severity 1 treatment, quarterly testing, post-use rotation, session revocation, and formal audit | Vultr portal, hardware MFA, safes, alerting, audits | HIGH | High; strong vendor coupling and manual process risk |

## 4. Cross-document dependencies

### Assumes these already exist

| Dependency | Why this auth spec depends on it | Likely owner |
|---|---|---|
| Kong public ingress layer | Required for JWT validation and propagation of `x-user-id` and `x-environment-id` into upstream services | `platform-v2.md` |
| Kubernetes/VKE platform foundation | Required for controllers, secrets, sidecars, NetworkPolicies, and auth service deployment targets | `platform-v2.md` |
| Crossplane VKE provisioning pipeline | Required because node bootstrap trust starts inside the VKE cluster composition | `platform-v2.md` |
| FluxCD reconciliation layer plus ingress-controller readiness gate | Required because auth services are configured only after prerequisite in-cluster services are ready | `gitops.md` + `platform-v2.md` |
| Central GitOps monorepo and PR workflow | Required for declarative Pomerium policy administration | `gitops.md` |
| CI system capable of `terraform plan` commentary on PRs | Required by the GitOps policy administration workflow | `gitops.md` |
| Central observability stack: Elasticsearch, Kibana, Grafana, Elastic APM | Required by the structured logging contract and the SRE correlation workflow | `platform-v2.md` |
| Central metrics and alerting stack: vmagent, vmalert | Required by the metrics and alert publication contracts | `platform-v2.md` |
| Kafka event bus and the `platform-alerts` topic | Required by the auth alert publication contract and the StackStorm workflow | `gitops.md` + `platform-v2.md` |
| StackStorm alert-consumer automation path | Required because incident handling begins with a contextualized StackStorm alert | `platform-v2.md` or ops runbooks |
| Self-hosted Infisical plus Infisical Operator | Required because every secret-handling rule assumes this is the only supported secret source | `platform-v2.md` or secrets spec |
| Internal applications that can host a local Cedar agent and emit standard logs | Required for the application-layer authorization contract to be implementable | App/service specs outside this document |
| Developer workstations with browser access and CLI tooling installation capability | Required for the JIT SSH access flow using `pomerium-cli` and `step-cli` | End-user tooling/workstation standard |
| Vultr portal administration and audit-log export path | Required for the break-glass protocol and associated alerting | `platform-v2.md` or security operations spec |

### Provides these to other documents

| Provided contract/capability | What downstream docs or teams can rely on | Likely consumers |
|---|---|---|
| Single source of identity in Authentik | Stable user, group, and session authority for policy and audit references | App specs, platform ops, security/compliance |
| OIDC federation boundary | Standard identity issuance path for Kong, Pomerium, and step-ca token validation | Ingress, infra access, service auth specs |
| Edge identity context propagation (`x-user-id`, `x-environment-id`) | Standard upstream identity envelope for app logging, authorization, and observability, specifically mapping JWT `sub` to `x-user-id` and a custom environment claim to `x-environment-id` | App/API specs, observability design |
| Central fine-grained authorization API (`POST /is_authorized`) | Common enforcement protocol for apps and data-plane components | App/service specs |
| Node trust anchor model based on step-ca User CA injection | Predictable SSH trust bootstrap for newly provisioned nodes | Platform provisioning and node lifecycle specs |
| Structured auth log/metric/alert fields | Shared correlation keys for incident response and auditing, including `timestamp`, `service.name`, `userId`, `environmentId`, `trace_id`, `pomerium.route`, `pomerium.decision`, `stepca.serial`, and `stepca.type` | Observability and incident-management specs |
| GitOps policy administration model for access changes | Repeatable review-and-apply mechanism for infra access policy changes, including edits under `infrastructure/terraform/auth-plane/`, `pomerium_policy` resources, PR review, CI plans, and Flux apply | GitOps/process docs, ops runbooks |
| Break-glass governance model | Emergency fallback procedure and audit expectations outside the normal auth plane, including three-account maximum, envelope storage, two-person approval, Severity 1 handling, and quarterly tests | Security/compliance and disaster-recovery docs |

## 5. Implementation units

| Unit ID | Title | Description | Dependencies | Components involved | Estimated complexity | Can be parallelized with |
|---|---|---|---|---|---|---|
| `auth-secrets-infisical-sync` | Infisical-to-Kubernetes secret delivery | Configure the baseline secret path for the auth plane. This includes defining `InfisicalSecret` resources, ensuring the Infisical Operator materializes Kubernetes Secrets, and standardizing secret mounts so later units do not embed credential logic. | `external:platform-kubernetes-foundation`, `external:central-infisical` | Infisical, InfisicalSecret, Infisical Operator, Kubernetes Secret | M | `auth-cedar-opal-core`, `auth-observability-logging` |
| `auth-authentik-core` | Deploy Authentik as the identity source of truth | Stand up Authentik with user, group, and service-identity authority. This unit covers baseline tenancy, identity schema, and the assumption that all downstream policy references point back to Authentik-managed identities. | `auth-secrets-infisical-sync`, `external:platform-kubernetes-foundation` | Authentik, Kubernetes, Infisical | M | `auth-observability-logging` |
| `auth-authentik-mfa-oidc` | Enforce MFA and publish OIDC federation from Authentik | Configure mandatory MFA for human users and define Authentik as the sole OIDC provider used by downstream systems. This unit includes client registrations and token-validation trust for Kong, Pomerium, and step-ca. | `auth-authentik-core` | Authentik, MFA, OIDC, JWT | M | `auth-cedar-opal-core`, `auth-observability-logging` |
| `auth-kong-identity-context` | Validate JWTs at Kong and propagate identity context | Implement the ingress contract that validates Authentik-issued JWTs and injects `x-user-id` from JWT `sub` plus `x-environment-id` from a custom environment claim into upstream requests. This unit establishes the verified identity envelope that later app logging and Cedar enforcement rely on. | `auth-authentik-mfa-oidc`, `external:kong-public-ingress` | Kong API Gateway, Authentik, JWT, OIDC, HTTP | M | `auth-pomerium-core`, `auth-stepca-core` |
| `auth-pomerium-core` | Deploy Pomerium for identity-aware infrastructure access | Stand up Pomerium as the infrastructure gatekeeper with Authentik-backed OIDC re-authentication. This covers the base proxy deployment, trust configuration, and the coarse-grained network access layer that later route-specific units consume. | `auth-authentik-mfa-oidc`, `auth-secrets-infisical-sync`, `external:platform-kubernetes-foundation`, `external:ingress-controller-ready` | Pomerium, Authentik, OIDC, Kubernetes, Infisical | M | `auth-cedar-opal-core`, `auth-stepca-core` |
| `auth-pomerium-admin-ui-routes` | Protect internal admin UIs behind Pomerium | Define and publish Pomerium routes/policies for Grafana, Kibana, and Harbor. The deliverable is a working admin-UI access boundary that inherits the OIDC re-authentication rules from the Pomerium core deployment. | `auth-pomerium-core` | Pomerium, Grafana, Kibana, Harbor | S | `auth-pomerium-tcp-routes`, `auth-cedar-opal-core`, `auth-observability-logging` |
| `auth-pomerium-tcp-routes` | Broker non-HTTP TCP access through Pomerium | Configure Pomerium for SSH, RDP, and direct database-style tunneled access over TCP-over-HTTPS. This unit creates the infrastructure routes that the JIT SSH client workflow and database access policies depend on. | `auth-pomerium-core` | Pomerium, SSH, RDP, TCP-over-HTTPS tunneling | M | `auth-pomerium-admin-ui-routes`, `auth-cedar-opal-core` |
| `auth-cedar-opal-core` | Deploy the central Cedar/OPAL authorization stack | Stand up the authorization control plane, including Cedar decisioning and OPAL distribution. This unit creates the runtime surface that later app integrations and identity sync flows bind to. | `auth-secrets-infisical-sync`, `external:platform-kubernetes-foundation` | OPAL, Cedar, Kubernetes, Infisical | M | `auth-pomerium-core`, `auth-stepca-core`, `auth-observability-logging` |
| `auth-opal-authentik-sync` | Synchronize Authentik identities into OPAL/Cedar | Implement OPAL data fetchers or equivalent sync logic so Cedar decisions can use current Authentik user/group attributes. This is the bridge between the source-of-truth IdP and the fine-grained authorization engine. | `auth-authentik-core`, `auth-cedar-opal-core` | Authentik, OPAL, Cedar, ABAC | M | `auth-observability-logging`, `auth-gitops-policy-pipeline` |
| `auth-app-pep-integration` | Instrument applications as Cedar policy enforcement points | Add the `/is_authorized` query pattern to one or more applications, sending `principal`, `action`, `resource`, and optional `context`, then enforcing and logging the returned `Allow` or `Deny` decision plus diagnostics. This unit is where app code begins enforcing central authorization instead of embedding authorization logic locally. | `auth-kong-identity-context`, `auth-cedar-opal-core`, `auth-opal-authentik-sync` | PEP, Cedar agent, Cedar Authorization Query format, HTTP, Kong API Gateway | M | `auth-pomerium-admin-ui-routes`, `auth-gitops-policy-pipeline` |
| `auth-stepca-core` | Deploy step-ca for short-lived SSH credential issuance | Configure step-ca as the SSH certificate authority, including OIDC token validation against Authentik and issuance of short-lived SSH certificates. This unit defines the certificate model but not yet the node trust bootstrap or client wrapper. | `auth-authentik-mfa-oidc`, `auth-secrets-infisical-sync` | Smallstep step-ca, Authentik, OIDC, SSH certificate | M | `auth-pomerium-core`, `auth-cedar-opal-core`, `auth-observability-logging` |
| `auth-node-bootstrap-ca-trust` | Inject step-ca trust into newly provisioned nodes | Extend the Crossplane Composition and Flux dependency graph so every new node trusts the step-ca User CA from first boot. This unit also codifies the ordering rule that waits for prerequisite in-cluster services before Terraform-based auth configuration runs. | `auth-stepca-core`, `external:crossplane-vke-provisioning`, `external:flux-reconciliation-layer` | Crossplane, Crossplane Composition, cloud-init, VKE, FluxCD terraform-controller, Flux Terraform custom resource, Flux Kustomization, ingress controller, sshd | M | `auth-observability-logging`, `auth-gitops-policy-pipeline` |
| `auth-jit-ssh-client-wrapper` | Deliver the end-user JIT SSH workflow | Build and package the workstation flow rooted in `ssh`, `ProxyCommand`, `pomerium-cli`, browser-based OIDC, `step ssh certificate`, and SSH-agent loading. This unit makes the certificate issuance and tunnel setup operational for developers and operators. | `auth-pomerium-tcp-routes`, `auth-stepca-core`, `auth-node-bootstrap-ca-trust` | ProxyCommand, access-wrapper script, pomerium-cli, web browser, step-cli, `step ssh certificate`, SSH agent, Pomerium, step-ca, sshd, SSH | L | `auth-observability-alert-routing`, `auth-breakglass-runbook` |
| `auth-observability-logging` | Emit standardized logs and metrics from auth components | Implement the structured JSON logging fields (`timestamp`, `level`, `service.name`, `message`, `userId`, `environmentId`, `trace_id`, plus component-specific fields), Prometheus metrics exposure, step-ca exporter sidecar, and `/metrics` NetworkPolicy restrictions. This unit makes the auth plane visible to the platform observability stack in a way the incident workflow can query. | `external:central-observability-stack`, `auth-pomerium-core`, `auth-stepca-core` | Elasticsearch, Kibana, Grafana, Prometheus exporter, Prometheus exposition format, vmagent, Kubernetes NetworkPolicy, Pomerium, step-ca | M | `auth-authentik-core`, `auth-cedar-opal-core`, `auth-node-bootstrap-ca-trust` |
| `auth-observability-alert-routing` | Route auth alerts onto the platform event bus | Configure vmalert rules and publication of auth-component alerts to Kafka using the standard alert event schema with `alert_name`, `severity`, `status`, and contextual labels, then verify StackStorm receives useful context. This unit operationalizes the observability contract for alerting rather than just metrics/log collection. | `auth-observability-logging`, `external:central-kafka`, `external:stackstorm-alert-entrypoint` | vmalert, Kafka, StackStorm | S | `auth-gitops-policy-pipeline`, `auth-breakglass-runbook` |
| `auth-gitops-policy-pipeline` | Automate reviewed Pomerium policy changes through GitOps | Implement the Terraform resource layout under `infrastructure/terraform/auth-plane/`, the `pomerium_policy` PR review pattern, CI `terraform plan` feedback as PR comments, and Flux `terraform apply` reconciliation needed to change access declaratively. This unit codifies the operator workflow into a repeatable delivery path. | `auth-pomerium-core`, `external:central-gitops-monorepo`, `external:central-ci-runner`, `external:flux-reconciliation-layer` | Terraform, GitOps monorepo, CI pipeline, FluxCD terraform-controller, Pomerium API, Pomerium | M | `auth-opal-authentik-sync`, `auth-node-bootstrap-ca-trust`, `auth-observability-alert-routing` |
| `auth-legacy-access-retirement` | Decommission VPN, bastion, and static-key access paths | Remove or disable the legacy trust model once the replacement path is functional. This unit should validate that Pomerium plus JIT certificates fully cover required access before retiring per-VPC VPNs, bastions, and static SSH keys. | `auth-jit-ssh-client-wrapper`, `auth-pomerium-admin-ui-routes`, `auth-gitops-policy-pipeline` | VPC, VPN, bastion hosts, static SSH keys, Pomerium, SSH certificate | M | `auth-breakglass-runbook` |
| `auth-breakglass-runbook` | Formalize and test emergency break-glass access | Create the operational procedure for up to three Vultr-portal emergency admins, printed passwords paired with hardware MFA in numbered tamper-evident envelopes, geographically distributed storage, two-person approval, quarterly tests, Severity 1 incident handling, post-use rotation, session revocation, and audit. This is mostly procedural work, but it depends on alert routing and audit-log ingestion to make activation visible. | `auth-observability-alert-routing`, `external:vultr-admin-surface` | Vultr Customer Portal, YubiKey, Vultr audit logs, StackStorm | S | `auth-jit-ssh-client-wrapper`, `auth-legacy-access-retirement` |

## 6. Outdated or questionable elements

1. No product versions are pinned for Authentik, Pomerium, OPAL, Cedar, step-ca, Kong, Flux, or Infisical. Modernization work will need a fresh compatibility matrix because the document is product-specific but version-agnostic.
2. The design is tightly coupled to Vultr and VKE, including the normal bootstrap path and the emergency break-glass path. If the platform vendor changes, both steady-state and disaster-recovery procedures change with it.
3. The document hardcodes FluxCD `terraform-controller` and Flux Terraform custom resources as the reconciliation mechanism. That controller surface should be revalidated for April 2026 because Terraform-on-Flux patterns have shifted over time.
4. The incident workflow assumes StackStorm as the alert entry point without explaining why that tool remains the right orchestration layer. This should be checked against the current operations stack rather than carried forward by inertia.
5. The observability design assumes Elasticsearch, Kibana, Grafana, and Elastic APM all remain the canonical logging/tracing surfaces. That may duplicate or conflict with the current platform-wide observability choices.
6. The JIT SSH path depends on a workstation-local chain of `ProxyCommand`, a custom wrapper, `pomerium-cli`, browser-driven OIDC, and `step-cli`. That is operationally plausible but fragile if workstation standards or CLI behaviors have changed.
7. The document references a "Declarative Policy Management Contract" in the GitOps workflow, but that contract is not actually defined in the Contracts section. Downstream teams would inherit an unresolved reference.
8. Application JWTs are described as "potentially longer-lived" but the document never defines their TTL, refresh, revocation, or theft-response model. That omission is risky because the gateway split depends on the JWT boundary being well understood.
9. Node trust is established by boot-time injection of the step-ca User CA key, but no rotation/remediation story is specified if the CA changes or a node drifts. The trust bootstrap is concrete, but lifecycle management is incomplete.
10. The break-glass procedure uses direct non-federated administrator accounts in the Vultr Customer Portal, which intentionally bypasses the entire identity plane. That may be necessary, but it also makes vendor lock-in part of the emergency recovery model.
11. Several contracts duplicate concerns likely owned elsewhere: Kong ingress, GitOps reconciliation, Kafka alert publication, and the observability field schema. Before modernization, these overlaps need explicit boundary decisions so the auth spec does not quietly fork platform-wide standards.

## 7. Missing elements

1. No migration plan is defined from existing VPN/bastion/static-key access to the new Pomerium plus step-ca model, including rollback criteria.
2. No high-availability topology is specified for Authentik, Pomerium, OPAL/Cedar, step-ca, Infisical Operator, or supporting data stores.
3. Failure modes are underspecified. The document does not say what applications do if the local Cedar agent is unavailable, what happens when OPAL sync lags, or how infra access behaves during partial Authentik or step-ca outages.
4. Certificate lifecycle details are incomplete. The document gives an example 5-minute TTL but no renewal policy, clock-skew tolerance, revocation flow, or user experience for long-running sessions.
5. Token lifecycle details are incomplete. Kong validates JWTs, but token issuance lifetimes, refresh behavior, revocation, and audience/scope boundaries are omitted.
6. Scaling limits are absent. There are no throughput, latency, concurrency, or tunnel-capacity targets for Pomerium, Cedar agent checks, step-ca issuance, or alert pipelines.
7. Cost modeling is absent. The document does not estimate steady-state cost for the auth stack, observability volume from structured logs, or operational cost of always-on controllers and proxies.
8. Secret and key backup/recovery are missing. step-ca private-key backup, Infisical disaster recovery, and restore/rotation procedures are not described.
9. Operational runbooks are incomplete. The SRE incident workflow is illustrative, but there are no concrete runbooks for auth outages, certificate issuance failures, OPAL data corruption, or compromised service credentials.
10. Monitoring is specified at the shape level but not at the operational level. Alert thresholds, SLOs, dashboards, and ownership for auth-component alerts are not defined.
11. Compliance and retention expectations are missing. The document requires structured logs and audits but does not define retention periods, access controls, or evidentiary handling for security investigations.
12. Application integration coverage is thin. The document defines the Cedar query contract but does not specify client libraries, retry semantics, caching rules, or how multiple services should normalize principal/resource naming.
13. The break-glass protocol has no automated validation scope beyond "tested on a quarterly basis." It does not define test evidence, observers, acceptance criteria, or the boundary between simulation and real portal access.

## 8. Raw statistics

- Total components mentioned: 62
- Total architectural decisions: 34
- Total implementation units: 18
- Total cross-document dependencies: 22
- Total outdated/questionable flags: 11
