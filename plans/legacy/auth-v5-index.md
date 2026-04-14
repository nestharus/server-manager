## 1. Scope and document intent

Explicitly, `auth-v5` defines the platform's "Authentication (AuthN) and Authorization (AuthZ) subsystem" as a definitive technical specification and canonical reference for engineering, operations, and security. It covers identity, infrastructure access, fine-grained authorization, observability, secrets, operational workflows, and emergency access.

Inference: this is a prescriptive architecture/specification artifact, not an implementation plan. It assumes a broader platform already exists and focuses on the access-control layer's contracts with that broader platform rather than defining the entire platform end to end.

## 2. Component inventory

| Component | Kind | Role in document | Notes |
| --- | --- | --- | --- |
| Unified Identity-Driven Access and Control Plane | Internal subsystem | The overall AuthN/AuthZ control plane being specified | Explicit top-level system name |
| Authentication (AuthN) subsystem | Internal subsystem | Authentication half of the control plane | Explicit scope boundary |
| Authorization (AuthZ) subsystem | Internal subsystem | Authorization half of the control plane | Explicit scope boundary |
| Authentik | Product/service | Exclusive identity provider and source of truth for identities | Explicitly selected technology |
| Multi-Factor Authentication (MFA) | Security control | Mandatory second factor for human users in Authentik | Explicitly required for humans |
| OpenID Connect (OIDC) | Protocol | Federation protocol from Authentik to downstream systems | Explicitly required |
| Pomerium | Product/service | Identity-aware access proxy for infrastructure and admin surfaces | Explicitly selected technology |
| TCP-over-HTTPS tunneling | Protocol/transport | Transport Pomerium uses to broker non-HTTP sessions | Explicit capability callout |
| SSH | Protocol | Primary JIT infrastructure access protocol and certificate target | Explicit use-case and contract target |
| RDP | Protocol | Additional non-HTTP access protocol brokered by Pomerium | Explicitly named but not deeply specified |
| Direct database connections | Access mode | Additional non-HTTP access path brokered by Pomerium | Explicitly named but not deeply specified |
| Grafana | Product/service | Example internal administrative UI protected by Pomerium | Explicit example |
| Kibana | Product/service | Example internal administrative UI and incident response query surface | Explicit example |
| Harbor | Product/service | Example internal administrative UI protected by Pomerium | Explicit example |
| JSON Web Tokens (JWTs) | Token format | Application-session credentials validated at Kong and intentionally separated from infra credentials | Explicit trust-boundary element |
| Kong API Gateway | Product/service | Primary public ingress gateway for north-south application traffic | Explicit contract participant |
| OPAL | Product/service | Real-time policy-data sync/control component in the authorization stack | Explicitly selected technology |
| Cedar | Policy engine/language | Fine-grained authorization decision engine and policy format | Explicitly selected technology |
| Attribute-Based Access Control (ABAC) | Authorization model | Fine-grained decision model for application and data-plane operations | Explicitly named control model |
| OPAL data fetchers | Internal integration component | Synchronize Authentik identity attributes into the authorization system | Explicit mechanism |
| Smallstep step-ca | Product/service | Ephemeral certificate authority for JIT SSH access | Explicitly selected technology |
| step-ca User CA | PKI component | CA public key trusted by nodes for SSH certificate validation | Explicit contract element |
| Application plane | Internal platform layer | Layer where application requests are authorized | Explicit architectural layer |
| Data plane | Internal platform layer | Layer where data operations such as database queries are authorized | Explicit architectural layer |
| Management plane | Internal platform layer | Sensitive admin surface protected by Pomerium | Explicit architectural layer |
| Crossplane | Product/service | Infrastructure provisioner for cluster creation | Explicit contract participant |
| Vultr Kubernetes Engine (VKE) | Provider-managed platform | Cluster substrate provisioned by Crossplane | Explicit provider/platform choice |
| FluxCD terraform-controller | Product/controller | Reconciler that configures AuthN/AuthZ services after infra readiness | Explicit controller choice |
| cloud-init | Bootstrap mechanism | Injects SSH CA trust material during node bootstrap | Explicit mechanism |
| Flux Terraform custom resource | CRD/object | Declarative unit for Terraform-based reconciliation | Explicit dependency-management subject |
| Flux Kustomization resource | CRD/object | Declarative prerequisite dependency target for Terraform resources | Explicit dependency-management subject |
| ingress controller | Cluster service | Example prerequisite service that must exist before later reconciliation | Explicit example dependency |
| Structured JSON logging | Logging contract | Mandatory log output format for AuthN/AuthZ components | Explicit observability contract |
| Elasticsearch cluster | Product/service | Central destination for structured logs | Explicit observability dependency |
| Prometheus exposition format | Metrics protocol | Mandatory metrics interface for AuthN/AuthZ components | Explicit observability contract |
| Prometheus exporter | Sidecar/service | Dedicated metrics exporter required for step-ca | Explicit implementation requirement |
| Kubernetes NetworkPolicy | Kubernetes primitive | Restricts access to protected metrics endpoints | Explicit observability hardening |
| vmagent | Product/service | Sole allowed scraper for `/metrics` endpoints | Explicit observability dependency |
| vmalert | Product/service | Alert generator whose outputs must publish to Kafka | Explicit observability dependency |
| Kafka | Product/service | Central alert transport | Explicit observability dependency |
| `platform-alerts` Kafka topic | Messaging channel | Mandatory destination for alert events | Explicit contract element |
| System Alert Event JSON schema | Event contract | Required alert payload format | Explicit contract element |
| Infisical | Product/service | Central self-hosted secrets manager | Explicitly selected technology |
| InfisicalSecret custom resource | CRD/object | Sole declarative sync mechanism from Infisical into Kubernetes | Explicit implementation choice |
| Infisical Operator | Operator/controller | Materializes native Kubernetes `Secret` objects | Explicit implementation choice |
| Kubernetes Secret objects | Kubernetes primitive | Runtime secret mount target for components | Explicit contract participant |
| Policy Enforcement Point (PEP) | Architectural role | Role each application must implement for fine-grained authorization | Explicit integration role |
| local Cedar agent | Sidecar/local service | Local authorization endpoint applications call synchronously | Explicit integration component |
| Cedar Authorization Query format | Interface/schema | Standard request format for authorization checks | Explicit API contract |
| `/is_authorized` endpoint | HTTP API endpoint | Standard authorization endpoint for application checks | Explicit API contract |
| central GitOps monorepo | Repository/control surface | Source of truth for declarative access policy changes | Explicit workflow dependency |
| Terraform | IaC tool | Auth-plane policy definition and reconciliation medium | Explicit workflow dependency |
| `pomerium_policy` resource | IaC resource | Declarative object used to express Pomerium policy changes | Explicit workflow artifact |
| StackStorm | Product/service | Consumer/delivery point for contextualized alerts in the incident workflow | Explicit workflow dependency |
| Elastic APM | Product/service | Trace backend used for root-cause investigation | Explicit workflow dependency |
| ProxyCommand | SSH client feature | Hook that intercepts SSH and launches the JIT access flow | Explicit workflow element |
| access-wrapper script | Internal client component | Platform-maintained script that orchestrates the JIT SSH flow | Explicit workflow element |
| `pomerium-cli` | CLI tool | Handles browser-based authentication and tunnel establishment | Explicit workflow element |
| `step-cli` | CLI tool | Requests SSH certificates and loads them into the SSH agent | Explicit workflow element |
| SSH agent | Local security component | Holds newly minted credentials during a developer session | Explicit workflow element |
| `sshd` daemon | Server component | Validates SSH certificates against the trusted CA key | Explicit workflow element |
| break-glass user accounts | Emergency access mechanism | Last-resort provider-side access path outside the normal stack | Explicit emergency protocol |
| Vultr Customer Portal | Provider control plane | Location where break-glass accounts live | Explicit provider dependency |
| YubiKey | Hardware token | Example physical MFA factor for break-glass accounts | Explicit emergency protocol element |
| Vultr audit logs | Audit source | Input used to detect and alert on break-glass usage | Explicit emergency protocol dependency |
| per-VPC VPNs | Legacy access mechanism | Explicitly deprecated network-perimeter access model | Named as a decommission target |
| bastion hosts | Legacy access mechanism | Explicitly deprecated network-perimeter access model | Named as a decommission target |
| static SSH keys | Legacy credential type | Explicitly deprecated standing credential model | Named as a decommission target |

## 3. Architectural decisions

| Decision | Evidence from document | Rationale in document | Confidence | Modernization risk |
| --- | --- | --- | --- | --- |
| Centralize access under a single identity-driven control plane | "Establish a single, identity-driven policy and control plane that governs all access" | Unifies authentication, authorization, and audit so every action can be correlated to a verified identity | high | medium |
| Reject network-location trust as an authorization primitive | ZTNA definition says all decisions must be based on verified identity and context, "rather than network location" | Eliminates trust based on being "inside" a VPC or network perimeter | high | low |
| Decommission VPN and bastion-based infrastructure access | ZTNA implication explicitly requires decommissioning "per-VPC VPNs" and "bastion hosts" using static credentials | Legacy perimeter models are treated as incompatible with the target security posture | high | low |
| Replace standing infrastructure credentials with JIT credentials | JIT definition grants credentials only when needed and only for minimum duration | Reduces the credential-theft attack window | high | low |
| Make Authentik the exclusive identity source of truth | Authentik "serves as the exclusive and single source of truth for all user and service identities" | Keeps all downstream access decisions anchored to one authoritative identity system | high | medium |
| Require MFA for all human identities | Authentik "enforces mandatory Multi-Factor Authentication (MFA) for all human users" | Adds a direct defense against credential compromise | high | low |
| Make Authentik the sole OIDC provider | Authentik "acts as the sole OpenID Connect (OIDC) provider" | Standardizes downstream identity federation and claims | high | medium |
| Require all authorization policies to reference Authentik-managed identities only | "All authorization policies throughout the platform MUST reference identities that are exclusively managed within Authentik" | Preserves integrity of the single-source-of-truth model | high | medium |
| Use Pomerium as the coarse-grained infrastructure gatekeeper | Pomerium "serves as the primary technical enabler" of ZTNA and acts as the Policy Enforcement Point for coarse-grained access | Creates an identity-based perimeter around sensitive infrastructure resources | high | medium |
| Force full OIDC re-authentication for every new infrastructure session | Pomerium "enforces a full OIDC re-authentication flow with Authentik for every new infrastructure session" | Explicitly decouples infra access from longer-lived application JWTs and limits token-theft blast radius | high | medium |
| Use Pomerium for both non-HTTP sessions and internal admin UIs | Pomerium brokers "SSH, RDP, and direct database connections" and secures "Grafana, Kibana, and Harbor" | Keeps human-to-infrastructure and admin-surface access behind one identity-aware gate | high | medium |
| Use OPAL/Cedar for fine-grained runtime ABAC | OPAL/Cedar provides fine-grained ABAC for "application-layer API requests" and "internal data-plane operations" | Enforces least privilege beyond coarse role or network checks | high | medium |
| Decouple authorization logic from application code | OPAL/Cedar "decouples authorization logic from application code" and manages policies as code | Lets policy be updated, audited, and reasoned about independently of app deployments | high | low |
| Continuously synchronize identity attributes from Authentik into the authorization engine | OPAL uses data fetchers to synchronize identity attributes "in real time" | Keeps authorization decisions current with user status and group membership | high | medium |
| Issue minute-scale ephemeral SSH certificates from step-ca | step-ca mints "ephemeral, short-lived SSH certificates" with TTL "typically on the order of minutes" | Implements JIT access and removes static-key operational/security burden | high | medium |
| Invoke step-ca through a client-side pre-SSH workflow | step-ca is "invoked by a client-side script after a user authenticates via Pomerium and Authentik, but before the final SSH connection" | Keeps the JIT certificate issuance tightly coupled to the authenticated session | high | medium |
| Deliberately separate application and infrastructure trust domains | The document contrasts Kong + JWTs for application access with Pomerium + interactive OIDC + SSH certificates for infrastructure access | Containment: a stolen web JWT should not grant infrastructure access | high | high |
| Make Kong the designated north-south application ingress gateway | "The Kong API Gateway is the designated primary Ingress Gateway for all public-facing, north-south application API traffic" | Captures verified identity at the edge and propagates it inward | high | medium |
| Standardize identity propagation via `x-user-id` and `x-environment-id` headers | Kong "MUST inject" those headers after JWT validation | Provides a common identity/environment context for downstream observability and authorization | high | medium |
| Split infra provisioning from auth-plane configuration between Crossplane and FluxCD | "Crossplane is solely responsible for provisioning" VKE, while Flux terraform-controller configures AuthN/AuthZ services once ready | Enforces separation of concerns and staged reconciliation | high | high |
| Bootstrap node SSH trust at creation time via injected step-ca CA material | The Crossplane Composition "MUST include a cloud-init configuration step" injecting the step-ca User CA public key | Makes every node trust JIT-issued SSH certificates from birth without manual key distribution | high | high |
| Encode reconciliation ordering declaratively with Flux `dependsOn` | Flux Terraform resources "MUST use FluxCD's dependsOn clause" on prerequisite Kustomizations | Prevents race conditions during environment provisioning | high | medium |
| Standardize structured JSON logging to stdout for all AuthN/AuthZ components | All components, especially Pomerium and step-ca, "MUST emit logs in a structured JSON format to the container stdout" | Enables cross-component correlation during incidents | high | medium |
| Standardize Prometheus metrics and use a dedicated step-ca exporter | All components "MUST expose operational metrics in the Prometheus exposition format"; "A dedicated Prometheus exporter MUST be deployed as a sidecar for step-ca" | Enables uniform scraping and alerting across the auth plane | high | medium |
| Lock down metrics endpoints with Kubernetes NetworkPolicy | `/metrics` "MUST be secured" to allow inbound traffic only from `vmagent` pods | Limits observability surface exposure | high | medium |
| Publish alert events through Kafka using a standard schema | Alerts from `vmalert` "MUST be published to the central platform-alerts Kafka topic" and conform to the System Alert Event schema | Makes alert handling part of a shared, machine-readable platform event plane | high | medium |
| Centralize secret storage in self-hosted Infisical and sync declaratively into Kubernetes | Secrets "MUST be stored and managed exclusively" in Infisical; `InfisicalSecret` is the "sole declarative mechanism"; components mount Kubernetes `Secret`s and do not call Infisical directly | Eliminates secret sprawl and centralizes audit/rotation control | high | medium |
| Require applications to synchronously consult a local Cedar agent before protected operations | Applications "MUST be instrumented" as PEPs and "MUST make a synchronous HTTP POST request" to `/is_authorized`; outcome "MUST be logged" | Extends centralized policy enforcement into the application and data plane | high | medium |
| Manage Pomerium access policy changes through GitOps and Terraform | Workflow modifies `.tf`, opens PR, CI runs `terraform plan`, and Flux terraform-controller later applies | Produces peer review, audit trail, and automatic deployment from code | high | medium |
| Intentionally keep a high-friction provider-side break-glass path outside the normal auth stack | Break-glass "intentionally and completely bypasses" the stack and uses at most three "non-federated user accounts" in the Vultr portal | Preserves last-resort access during total failure of primary auth systems | high | high |
| Treat any break-glass use as a Sev1-style, tightly governed event | Protocol requires two-person approval, automatic Severity 1 classification, quarterly testing, and post-use rotation/revocation/audit | Makes emergency access visible, auditable, and difficult to abuse | high | medium |

## 4. Implementation units

| Unit | What would need to be built/configured | Dependencies | Why it exists |
| --- | --- | --- | --- |
| Authentik identity source configuration | Configure Authentik as the authoritative store for users, groups, service identities, MFA, and OIDC federation | Authentik, MFA, OIDC, identity data model defined elsewhere | Establishes the single source of truth for identity |
| Identity claims and context model | Define and emit the claims used downstream, including `sub` and the custom `environmentId` claim | Authentik, Kong, downstream application contracts | Makes identity and environment context portable across the platform |
| Kong edge validation and context propagation | Configure Kong to validate Authentik JWTs and inject `x-user-id` and `x-environment-id` into upstream requests | Kong, Authentik, JWT claim model, upstream services | Captures verified identity at the edge and propagates it inward |
| Pomerium infrastructure-access deployment | Deploy and configure Pomerium routes and policies for SSH, RDP, direct database access, and protected admin UIs | Pomerium, Authentik, infrastructure targets, admin UI inventory | Provides the coarse-grained identity-aware gateway for human access |
| Pomerium per-session re-authentication flow | Configure session behavior so every new infrastructure session forces a fresh OIDC login | Pomerium, Authentik, OIDC session policy | Enforces the application-vs-infrastructure trust boundary |
| OPAL/Cedar control plane deployment | Deploy the real-time authorization stack and its policy evaluation surface | OPAL, Cedar, policy repository/process not defined here | Supplies fine-grained authorization decisions at runtime |
| Authentik-to-OPAL attribute synchronization | Implement OPAL data fetchers and the data mapping from Authentik users/groups/status into Cedar entities/attributes | Authentik, OPAL data fetchers, Cedar schema | Keeps policy decisions current with identity state |
| Application PEP integration | Instrument each relevant application to call the local Cedar agent's `/is_authorized` endpoint before protected operations and log decisions | Application services, local Cedar agent, Cedar query format, application logging | Extends centralized authorization into the application/data plane |
| step-ca PKI and SSH CA setup | Deploy `step-ca`, configure SSH certificate issuance, TTLs, and trust materials | Smallstep step-ca, Authentik, SSH certificate model | Implements JIT credential issuance for infrastructure access |
| Developer JIT SSH client toolchain | Build/configure the `ProxyCommand`, access-wrapper script, `pomerium-cli`, `step-cli`, and SSH-agent handling on developer machines | Developer workstation bootstrap, Pomerium, Authentik, step-ca | Turns the JIT SSH flow into an operable user journey |
| Node bootstrap trust injection | Add `cloud-init` logic in Crossplane-managed node provisioning to trust the step-ca User CA | Crossplane, VKE, cloud-init, step-ca User CA | Ensures new nodes accept JIT-issued certificates immediately |
| Flux auth-plane reconciliation layer | Define Terraform resources and Flux terraform-controller objects, including `dependsOn` ordering against prerequisite Kustomizations | FluxCD terraform-controller, Terraform, Crossplane readiness, ingress controller | Separates provisioning from auth-plane configuration and prevents race conditions |
| Structured logging conformance | Configure AuthN/AuthZ components to emit the required JSON log fields to stdout | Pomerium, step-ca, shared logging stack, field schema | Makes cross-component incident correlation possible |
| Metrics and exporter integration | Expose Prometheus-format metrics for each component and run a dedicated exporter sidecar for step-ca | Prometheus-compatible components, exporter, vmagent, NetworkPolicy | Standardizes operational telemetry |
| Metrics-surface hardening | Write Kubernetes `NetworkPolicy` rules that restrict `/metrics` to `vmagent` only | Kubernetes networking layer, vmagent placement | Reduces observability endpoint exposure |
| Alert event publication | Configure `vmalert` outputs and Kafka publishing so alert messages land on `platform-alerts` with the required schema | vmalert, Kafka, System Alert Event contract | Feeds the platform's shared incident pipeline |
| Secret-sync plumbing | Store required secrets in Infisical, define `InfisicalSecret` resources, materialize Kubernetes `Secret`s, and mount them into deployments | Infisical, Infisical Operator, Kubernetes Secrets | Centralizes secret management without runtime direct API access |
| GitOps access-policy administration path | Define repo layout, Terraform workflow, PR review path, CI `terraform plan` commenting, and Flux reconciliation for policy changes | central GitOps monorepo, Terraform, CI system, FluxCD | Makes access changes declarative, reviewable, and auditable |
| Protected admin UI onboarding | Put Grafana, Kibana, Harbor, and similar admin surfaces behind Pomerium | Pomerium, admin UI inventory, Authentik | Extends identity-aware access to management tooling |
| Correlated incident-response data path | Ensure alerts, logs, metrics, and traces can be joined on shared labels like `userId`, `environmentId`, and `trace_id` | StackStorm, Kafka, Elasticsearch/Kibana, Grafana, Elastic APM, app log propagation | Makes the promised SRE workflow actually possible |
| Break-glass account provisioning and custody | Create the limited provider-side admin accounts, MFA hardware assignment, envelope/seal process, and approval runbook | Vultr Customer Portal, YubiKey, organizational physical-security process | Preserves a last-resort access path during full auth-plane failure |
| Break-glass audit and alert automation | Ingest provider audit logs and generate immediate high-priority alerts for any break-glass usage | Vultr audit logs, alerting pipeline, leadership escalation process | Makes emergency access highly visible and reviewable |
| Non-SSH infrastructure access parity | Implement the RDP and direct-database brokered flows that are named in scope but not illustrated in detail | Pomerium, target protocols/services, policy model | Completes the document's stated non-HTTP access scope |

## 5. Cross-document dependencies

| Dependency | Depends on what | Why it is cross-document | Confidence |
| --- | --- | --- | --- |
| Auth v4 lineage | The earlier "Auth v4" design proposal | `auth-v5` is explicitly a refactoring of `Auth v4`, so some intent and assumptions live outside this file | high |
| Public ingress architecture | Kong gateway configuration, upstream trust model, and service ingress conventions | The document specifies Kong's role but not the broader ingress architecture or service-side trust enforcement | high |
| Provider/infrastructure model | Vultr and VKE platform choices | The auth design assumes a specific cluster provider/control plane owned by another platform layer | high |
| Provisioning compositions | Crossplane compositions for VKE clusters and node bootstrap | This file imposes requirements on provisioning artifacts but does not define them in full | high |
| GitOps/controller topology | FluxCD controllers, CRDs, and reconciliation patterns | The auth design depends on an existing Flux-based control plane defined elsewhere | high |
| Prerequisite cluster services | Ingress controller and other in-cluster prerequisites | These prerequisites are referenced but not defined in this document | high |
| Logging platform | Elasticsearch/Kibana ingestion, indexing, retention, and querying conventions | This file specifies log shape and destination but not the logging platform design | high |
| Metrics and alerting platform | Prometheus-compatible scraping, `vmagent`, `vmalert`, Kafka, and downstream consumers | The contract assumes a larger observability and eventing stack defined elsewhere | high |
| Trace platform | Elastic APM and distributed tracing instrumentation | The SRE workflow depends on tracing infrastructure not specified here | high |
| Incident automation layer | StackStorm delivery/automation behavior | The workflow consumes alerts through StackStorm, but StackStorm configuration is out of scope here | medium |
| Secrets platform | Self-hosted Infisical deployment and its operator lifecycle | This file mandates Infisical usage but does not define the platform that runs it | high |
| CI system | The unnamed CI pipeline that runs `terraform plan` and comments on PRs | The workflow requires CI behavior but does not name the executor/tooling | high |
| Application contracts | Service-specific PEP integrations, logging, and propagation of identity/trace context | The auth design depends on application teams implementing contracts outside this document | high |
| Environment model | The meaning and issuance path of `environmentId` | The header/claim is required here, but the broader environment taxonomy is defined elsewhere | medium |
| Developer workstation bootstrap | Distribution and maintenance of SSH client config, wrapper scripts, and CLIs | The JIT SSH flow assumes managed client tooling outside the auth-plane spec | medium |
| Provider audit-log pipeline | Path from Vultr audit logs into the platform alerting system | Break-glass alerting depends on provider-log ingestion defined elsewhere | medium |
| Physical security and approvals | Safes, tamper-evident envelopes, and two-chain approval process | The emergency protocol depends on organizational controls outside the software platform | high |

## 6. Outdated or questionable items

| Item | Why questionable | Likely modernization direction |
| --- | --- | --- |
| Vultr / VKE-specific framing | The document hard-codes Vultr and VKE across provisioning and break-glass flows, while newer guidance says provider choice may move beyond the original Vultr framing | Preserve the access-control intent but introduce provider-agnostic abstractions around cluster provisioning and emergency access |
| `FluxCD terraform-controller` as the exact reconciliation mechanism | The document fixes not just `FluxCD` but a specific controller topology; that may be more rigid than the modern platform needs | Keep `Flux` as the preferred target over `Argo`, but re-evaluate whether `terraform-controller` remains the right implementation detail |
| Node-IP SSH as a first-class developer access path | The main developer journey assumes direct SSH to dynamically provisioned nodes, which may not survive a more managed or provider-abstracted runtime | Reconcile the JIT access model with the modern compute/runtime model rather than assume raw node SSH persists |
| Tool-specific admin UI inventory (`Grafana`, `Kibana`, `Harbor`) | The access pattern is durable, but the exact set of management tools is likely to drift | Preserve the rule "management UIs go behind the identity-aware proxy" while treating the tool list as replaceable |
| Elasticsearch/Kibana/Elastic APM coupling | The observability design is deeply tied to a specific logging and tracing stack | Preserve the correlation requirements (`userId`, `environmentId`, `trace_id`) while allowing observability backends to change |
| `StackStorm`-centric incident workflow | The SRE workflow names a specific automation/orchestration tool that may not remain canonical | Preserve the structured alert handoff, not necessarily the exact consumer |
| Provider-portal break-glass accounts | Emergency access is bound to the `Vultr Customer Portal`, which is incompatible with future provider changes | Keep the high-friction break-glass principle but detach it from a single provider control plane |
| Printed passwords + physical envelope storage | The design may still be valid for high-friction access, but it is operationally heavy and tightly coupled to one manual process | Preserve two-person control and tamper evidence while allowing the storage/runbook mechanics to evolve |
| Dedicated `Prometheus exporter` sidecar for `step-ca` | This is a very specific telemetry implementation assumption and may no longer be necessary or ideal | Re-validate the metrics exposure approach against current `step-ca` capabilities and platform standards |
| CI pipeline left unnamed | The workflow depends on CI behavior but never names the tool, which becomes a merge-time ambiguity | Preserve the user override that `Buildkite` is preferred over `Dagger` when the modernized platform fills this gap |
| Alternative GitOps substitutions during merge | This document is already `Flux`-based, but later merge work may encounter competing legacy specs | Preserve the user override that `Flux` is preferred over `Argo`; do not treat controller substitution as automatically open |
| `Auth v4` refactor lineage | Some choices may reflect inherited constraints from `Auth v4` rather than current platform needs | Re-test inherited assumptions during merge instead of treating the legacy lineage as authoritative |
| Legacy perimeter technologies (`per-VPC VPNs`, `bastion hosts`, `static SSH keys`) | They appear only as things to decommission, which can be lost if later merge work reads them as active dependencies | Preserve them as explicit anti-patterns / migration-away targets, not modern building blocks |
| Whole-document stability assumption | The document presents itself as definitive, but newer guidance says the modernized platform will likely differ materially from these legacy specs | Treat `auth-v5` as a rich legacy input, not as a document that can be lifted forward unchanged |

## 7. Missing or underspecified elements

| Gap | Why it matters | Confidence |
| --- | --- | --- |
| Service-to-service identity model | The goals explicitly include internal service-to-service communication, but the document mostly specifies human-to-infrastructure and application authorization flows | high |
| Non-human credential issuance and rotation | Service identities are named, but the issuance, storage, rotation, and verification path for those principals is not specified | high |
| Upstream trust-boundary hardening for Kong-injected headers | The document requires `x-user-id` and `x-environment-id` propagation but does not specify how upstream services reject spoofed headers or trust Kong as the sole injector | high |
| JWT session semantics | Token TTLs, refresh behavior, revocation, and logout semantics are not specified even though JWTs are central to the app-side trust model | high |
| `environmentId` semantics and authority | The claim/header is mandatory, but the source of truth, allowed values, and tenancy/environment model are not defined here | high |
| OIDC claim, audience, and JWKS details | The spec says OIDC is central, but it omits concrete audience, scope, claim-mapping, and key-rotation behavior | medium |
| Cedar schema and policy lifecycle | The document chooses OPAL/Cedar but does not define entity schema, policy repo layout, testing, versioning, or rollout rules | high |
| Failure behavior for OPAL data synchronization | Real-time sync is required, but staleness, outage, cache, and partial-failure behavior are not defined | high |
| step-ca PKI topology and recovery | The document names `step-ca` and CA trust injection but does not define root/intermediate layout, key custody, rotation, or disaster recovery | high |
| HA/DR expectations for Authentik, Pomerium, OPAL, and step-ca | The design is security-critical, but availability, backup, restore, and failover expectations are not specified | high |
| End-to-end RDP and direct-database flows | These protocols are explicitly in scope, but only SSH gets a detailed end-user journey | high |
| Application-side onboarding model | Applications must act as PEPs, but the deployment pattern for the local Cedar agent and app integration guidance is absent | high |
| Secret-rotation and bootstrap details | Infisical is mandated, but rotation cadence, bootstrap of operator credentials, and recovery flows are not described | medium |
| CI implementation choice | The workflow requires CI plan comments and PR integration, but the concrete system is absent; later merge must preserve the `Buildkite` over `Dagger` conflict marker | high |
| Provider abstraction boundary | The spec assumes Vultr/VKE everywhere and does not define what part of the design is provider-specific versus provider-neutral | high |
| Merge-time controller conflict handling | The document is `Flux`-specific, but it does not say how to reconcile competing legacy controller patterns; later merge must preserve the `Flux` over `Argo` conflict marker | medium |
| Break-glass audit closure | Break-glass alerts, rotation, and audits are mandated, but the full evidence chain and review artifact model are not specified | medium |

## 8. Raw statistics

- Total components mentioned: 68
- Total architectural decisions: 30
- Total implementation units: 23
- Total cross-document dependencies: 17
- Total outdated/questionable flags: 14
