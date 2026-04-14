# Pomerium + Smallstep scope and overlap

## 1. Executive summary

In a 2026 enterprise-leaning platform, Pomerium and Smallstep solve adjacent but different problems.

Pomerium is an identity-aware access proxy and policy-enforced gateway. Its job is to sit in front of applications, Kubernetes APIs, and selected TCP/UDP services, authenticate humans through an external IdP, and enforce access policy at request or session time. It is strongest for human access to internal systems: web apps, admin consoles, `kubectl`, SSH, and other operator-facing entry points.

Smallstep is PKI and workload identity infrastructure. Its job is to issue, renew, and manage short-lived X.509 and SSH certificates for workloads, devices, and sometimes humans. It is strongest for service-to-service authentication, mTLS, Kubernetes workload certificates, and certificate-backed access patterns where cryptographic identity matters more than browser SSO or route-level policy.

The tools complement each other more than they overlap. Pomerium can use mTLS and can secure TCP/SSH access, but it is not a full certificate lifecycle platform. Smallstep can issue human and workload certificates and integrate with OIDC, but it is not an application access gateway and does not replace per-request authorization in front of apps.

For this platform shape, both are justified only if the platform wants both:

- a dedicated human-access layer for internal apps and operator entry points
- a dedicated PKI/workload-identity layer for east-west mTLS and certificate automation

If the platform only wants one of those scopes, one tool becomes redundant. The older assumption that "auth stack" and "configuration management" collapse into one system does not hold up well in 2026; identity, access mediation, authorization, PKI, and edge concerns are now cleaner when separated.

## 2. Responsibility split table

| Concern | Pomerium | Smallstep |
| --- | --- | --- |
| Primary role | Identity-aware access proxy and policy gateway | PKI, certificate authority, workload/device identity |
| Core trust input | External IdP session and user/device context | Certificate issuance policy, attestation, ACME/OIDC/cloud identity inputs |
| Main object protected | Routes, apps, APIs, TCP/UDP entry points | Devices, workloads, services, hosts, users via certificates |
| Human web access | Strong fit | Indirect fit only |
| Human CLI/operator access | Strong fit for `kubectl`, SSH, TCP tunnels | Strong fit when using SSH or client certs, but not as a front-door proxy |
| Service-to-service auth | Limited/adjacent fit | Primary fit |
| Kubernetes ingress/app access | Strong fit | Indirect fit via cert issuance |
| Kubernetes workload identity | Not primary | Strong fit |
| mTLS | Can enforce/use it between clients, proxy, and upstreams | Issues and manages the certificates that make mTLS practical |
| Authorization | Route/session policy enforcement | Certificate issuance policy, not app access authorization |
| Identity provider | Depends on external IdP; not an IdP | Can consume OIDC for certificate issuance; not an IdP |
| Best platform position | North-south human access layer | East-west and workload trust layer |

## 3. Complement vs overlap analysis

### Complement

Pomerium fits the human-access side of the platform. Its own documentation describes it as an identity-aware proxy that secures applications, services, and workloads by verifying user identity, device state, and request context before access is granted. It also supports route-level authorization and can proxy Kubernetes API access, SSH, and non-HTTP TCP/UDP services. In practice, that makes it a gateway for people.

Smallstep fits the cryptographic identity side. `step-ca` is explicitly a CA for X.509 and SSH certificate management, with support for automated issuance and renewal for clients, servers, and Kubernetes workloads. Smallstep's Kubernetes material is centered on issuing and renewing workload certificates so pods and services can use mTLS inside and across clusters. In practice, that makes it a trust fabric for workloads and devices.

Used together, the clean split is:

- Pomerium authenticates the human and enforces access to the destination
- Smallstep establishes machine, workload, host, and sometimes user certificate identity underneath that path

That division aligns well with a platform that has Cloudflare at the edge, Kubernetes behind ingress, and a separate IdP such as Authentik or Logto.

### Overlap

There is some overlap, but it is narrower than it first appears.

Both touch authentication:

- Pomerium delegates human authentication to an IdP and can enforce access with JWTs, session state, and optional mTLS
- Smallstep can also use OIDC to issue certificates to humans and can issue SSH and X.509 credentials for access

Both can participate in SSH and mTLS:

- Pomerium can front SSH and other TCP services and apply access policy
- Smallstep can issue SSH certificates and mTLS certificates used by those services

Both can appear in Kubernetes stories:

- Pomerium secures access to Kubernetes APIs and services
- Smallstep secures identities of Kubernetes workloads themselves

### Where overlap stops

The important boundary is operational responsibility:

- Pomerium does not replace a CA, certificate inventory, or certificate automation layer
- Smallstep does not replace an identity-aware proxy that continuously authorizes app requests and brokered user sessions

Pomerium's own security model says it is not an identity provider. Smallstep's platform material likewise frames Smallstep as PKI and device/workload identity infrastructure rather than an IdP or network gateway. That is the core reason the two are usually complementary rather than duplicative.

## 4. Minimal recommended scope for this platform

For the platform described here, the minimal sane scope is:

- Use the external IdP such as Authentik or Logto for workforce identity and group claims.
- Use Pomerium only for human/operator access to internal applications and control planes:
  - internal web apps behind Kubernetes ingress
  - admin panels and dashboards
  - Kubernetes API access via `kubectl`
  - selected SSH or TCP services where brokered user access is preferable to direct network exposure
- Use Smallstep only for PKI and workload identity:
  - certificate authority and trust roots
  - workload certificates for Kubernetes and other internal services
  - service-to-service mTLS
  - optional SSH or user certificates where certificate-based operator access is desired

What this means in practice:

- Cloudflare remains the edge and public ingress layer.
- Pomerium sits behind that edge for identity-aware access to private/internal services.
- Smallstep provides the certificate lifecycle and workload trust that Pomerium can consume but should not own.

For service-to-service auth, prefer Smallstep over trying to stretch Pomerium into an east-west control plane. For human access to apps and operator endpoints, prefer Pomerium over trying to stretch Smallstep into an application gateway.

## 5. Risks and caveats

- Two systems means two policy surfaces. If Pomerium route policy, IdP group mapping, and a separate authorization system all encode similar rules, drift is likely.
- Pomerium overlaps more with Cloudflare Access than with Smallstep. If the edge plan eventually includes Cloudflare's identity-aware access products, Pomerium may become partly redundant on the human-access side.
- Smallstep overlaps more with existing service mesh PKI, cert-manager, or cloud-native CA offerings than with Pomerium. If the cluster stack already has a strong certificate and workload identity story, Smallstep may be optional rather than necessary.
- Do not confuse mTLS transport identity with application authorization. Smallstep proves which workload or device is calling; it does not decide business permissions inside the app.
- Do not confuse Pomerium policy with a general authorization platform. Pomerium is excellent for access gating at the edge of apps and services, but it is not a full replacement for application-level authorization or domain policy.
- Human certificate flows add operational sharp edges. Smallstep can issue user certificates via OIDC, but browser SSO and route mediation are still simpler in Pomerium for most internal web access.
- Pomerium can secure non-HTTP protocols, but that does not make it a substitute for workload identity or service mesh-style east-west trust.

## 6. Recommendation

Use both only if the platform explicitly wants both layers:

- Pomerium as the human-access gateway for internal apps, `kubectl`, SSH, and selected operator-facing services
- Smallstep as the PKI and workload-identity system for Kubernetes, service-to-service mTLS, and certificate lifecycle

If forced to minimize scope, the deciding question is straightforward:

- If the pressing problem is "how do humans securely reach internal systems with SSO and policy?" choose Pomerium first.
- If the pressing problem is "how do workloads and devices get strong cryptographic identity and mTLS without secret sprawl?" choose Smallstep first.

For the stated enterprise direction, my recommendation is:

- keep Pomerium narrowly scoped to human/operator access mediation
- keep Smallstep narrowly scoped to PKI, workload identity, and certificate-backed trust
- avoid treating either one as the platform's main identity system or universal authorization engine

That split still makes sense in 2026. What does not make sense is the older assumption that one "auth/config" layer should absorb identity, gatewaying, PKI, and authorization all at once.

## Sources

- Pomerium docs, "What is Pomerium?": https://www.pomerium.com/docs
- Pomerium docs, "Security & Threat Model": https://www.pomerium.com/docs/internals/security
- Pomerium docs, "Authorization and Policy Enforcement": https://www.pomerium.com/docs/capabilities/authorization
- Pomerium docs, "Kubernetes kubectl Integration": https://www.pomerium.com/docs/capabilities/kubernetes-access
- Pomerium docs, "Continuous Identity Verification at the Application Layer": https://www.pomerium.com/docs/capabilities/getting-users-identity
- Pomerium docs, "Mutual Authentication": https://docs.pomerium.com/docs/internals/mutual-auth
- Pomerium docs, "Clients for Tunneling Non-HTTP Protocols": https://docs.pomerium.com/docs/deploy/clients
- Smallstep docs, "`step-ca` server": https://smallstep.com/docs/step-ca/
- Smallstep docs, "How It Works": https://smallstep.com/docs/platform/how-it-works/
- Smallstep docs, "Single Sign-on Certificates": https://smallstep.com/docs/certificate-manager/oidc/
- Smallstep docs, "Kubernetes Autocert for Automatic TLS Setup": https://smallstep.com/docs/certificate-manager/kubernetes-tls/kubernetes-autocert/
