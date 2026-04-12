# Pomerium + Smallstep in 2026: scope, overlap, and whether Auth v5 still needs both

## Bottom line

As of April 11, 2026, **Pomerium has expanded materially since 2024**, especially around **native SSH**, **non-HTTP access**, **desktop/CLI route discovery**, and **Kubernetes deployment options**. But it still does **not** replace **Smallstep `step-ca`** as a general-purpose certificate authority.

The clean current split is:

- **Pomerium**: identity-aware access plane at L7/L5. It authenticates users and services, enforces access policy, proxies HTTP, can tunnel TCP/UDP, and now supports **native clientless SSH** with just-in-time user certificates signed by a Pomerium-managed SSH user CA.
- **Smallstep `step-ca`**: certificate issuance and PKI plane. It issues and renews **X.509** and **SSH** certs, exposes **ACME**, supports **OIDC**, **Kubernetes service account token** enrollment, **cert-manager**, **autocert**, and **Envoy SDS**.

So the answer to the core question is: **Pomerium has grown into part of Smallstep’s old SSH access territory, but it has not grown into Smallstep’s broader CA / PKI / workload identity role.**

## 1. Pomerium’s current capabilities, and what changed since 2024

Pomerium remains, first, an **identity-aware reverse proxy**. Its current docs describe it as an open-source identity-aware proxy that secures internal apps, servers, services, and workloads by continuously verifying identity, device state, and request context. In Kubernetes, its Ingress Controller provisions routes from `Ingress` resources and enforces access policies from annotations and CRDs. [Docs overview](https://docs.pomerium.com/docs), [Kubernetes ingress docs](https://www.pomerium.com/docs/k8s/ingress.html)

What changed since 2024 is that Pomerium is now visibly broader than “HTTP reverse proxy plus OIDC”:

- **Native SSH is now a first-class feature.** Current docs show Pomerium signing SSH user certificates with a configured `ssh_user_ca_key`, distributing the corresponding public key to upstream SSH servers, and letting users connect with ordinary `ssh user@route@pomerium-host` syntax after browser-based authentication. This is much closer to a zero-trust SSH broker than the older “TCP tunnel to port 22” model. [Native SSH docs](https://www.pomerium.com/docs/capabilities/native-ssh-access)
- **Non-HTTP access is more mature.** Pomerium now documents TCP and UDP tunneling over HTTP using `CONNECT` and `CONNECT-UDP`, with both CLI and desktop clients for access to databases and other services. [Non-HTTP docs](https://www.pomerium.com/docs/capabilities/non-http), [client docs](https://www.pomerium.com/docs/deploy/clients)
- **Desktop client and route discovery are operational products, not side notes.** The Routes Portal can feed the Desktop Client route configuration dynamically, which is useful for TCP/UDP routes. [Routes Portal docs](https://www.pomerium.com/docs/capabilities/routes-portal)
- **Kubernetes posture has hardened.** Pomerium now has explicit CRD-driven global config, Ingress Controller docs, and Gateway API support. [Global config](https://www.pomerium.com/docs/deploy/k8s/configure), [Gateway API](https://docs.pomerium.com/docs/deploy/k8s/gateway-api)
- **Recent releases show continued expansion beyond classic web proxying.** The `v0.31`/`v0.32` release lines added HTTP/3, UDP routing, and a large number of SSH-related improvements. [GitHub releases](https://github.com/pomerium/pomerium/releases)

What Pomerium still is **not**:

- It is **not** a general-purpose X.509 CA.
- It does **not** issue arbitrary workload certs for a mesh, cluster, or fleet in the way `step-ca` does.
- It does **not** replace cert-manager, ACME servers, or workload certificate automation systems.

On certificate management, Pomerium mainly **uses** certs rather than acting as the CA of record. Its certificate docs say it loads server/client certificates to secure user-to-Pomerium, intra-Pomerium, and Pomerium-to-upstream connections. It supports public-facing ACME automation via **Autocert**, but that is about obtaining TLS certs for Pomerium-managed domains, not about becoming your internal PKI. [Certificate settings](https://www.pomerium.com/docs/reference/certificates), [Autocert](https://www.pomerium.com/docs/reference/autocert)

## 2. Smallstep `step-ca` current capabilities

`step-ca` in 2026 is still clearly a **certificate authority server**. Smallstep’s current docs describe it as an online CA for automated **X.509 and SSH certificate management**, with configurable provisioners, templates, and multiple integrations. [step-ca overview](https://smallstep.com/docs/step-ca/)

Its current capabilities directly cover the Auth v5 concerns:

- **Ephemeral SSH certificates**: `step-ca` can issue SSH user and host certs. The `step ssh certificate` flow supports short-lived certs, host certs, custom principals, and OIDC-backed issuance. [SSH command reference](https://smallstep.com/docs/step-cli/reference/ssh/certificate/), [SSH tutorial](https://smallstep.com/docs/tutorials/ssh-certificate-login/)
- **mTLS / workload certs**: `step-ca` issues X.509 certs for TLS and mTLS, including short-lived certs for services, workloads, and humans. [step-ca overview](https://smallstep.com/docs/step-ca/)
- **ACME server**: `step-ca` has a native ACME provisioner, so it can act as a private ACME server for cert-manager, Caddy, Certbot, and other ACME clients. [Provisioners](https://smallstep.com/docs/step-ca/provisioners/), [ACME basics](https://smallstep.com/docs/step-ca/acme-basics)
- **OIDC integration**: its OIDC provisioner can authenticate certificate issuance using identity provider tokens. [Provisioners](https://smallstep.com/docs/step-ca/provisioners/)
- **Kubernetes cert-manager integration**: Smallstep documents two options, `step-issuer` or cert-manager’s ACME issuer against `step-ca`. [Integrations](https://smallstep.com/docs/step-ca/integrations/), [cert-manager with step-ca](https://smallstep.com/docs/tutorials/kubernetes-acme-ca/)
- **Kubernetes service account token to cert**: the `K8sSA` provisioner allows certificate requests authenticated with a Kubernetes service account token, and both `step ca certificate` and `step ssh certificate` support `--k8ssa-token-path`. [Provisioners](https://smallstep.com/docs/step-ca/provisioners/), [X.509 CLI ref](https://smallstep.com/docs/step-cli/reference/ca/certificate/), [SSH CLI ref](https://smallstep.com/docs/step-cli/reference/ssh/certificate/)
- **Container-native delivery patterns**: Smallstep’s ecosystem includes `step-issuer`, `autocert`, and `step-sds` for cert-manager, direct pod cert injection, and Envoy SDS. [Integrations](https://smallstep.com/docs/step-ca/integrations/)

So Smallstep’s role is still broad PKI: issuance, renewal, trust distribution patterns, and workload identity.

## 3. Exact overlap

There is real overlap, but it is narrower than “both do certificates.”

The overlap is:

- Both participate in **TLS-secured connections**.
- Both can be part of **mTLS** architectures.
- Both now touch **SSH certificate workflows**.

But they touch those areas at different layers.

### Overlap area A: TLS certificates

Pomerium can terminate TLS, do downstream mTLS, and present client certificates to upstream services. It can also obtain public-facing certs via ACME `autocert` in non-Kubernetes deployments. [TLS docs](https://www.pomerium.com/docs/capabilities/mtls-services), [Autocert](https://www.pomerium.com/docs/reference/autocert)

Smallstep, by contrast, is the system that **issues** the certificates and defines the trust chain. [step-ca overview](https://smallstep.com/docs/step-ca/)

So the overlap is operational, not architectural: **Pomerium consumes certs; Smallstep manufactures and rotates them.**

### Overlap area B: SSH

This is the biggest 2026 change.

Historically, Smallstep had the clearer story for ephemeral SSH certs. Now Pomerium’s Native SSH feature provides an on-demand flow where a user connects with a normal SSH client, authenticates via browser/OIDC, and Pomerium signs an SSH user cert using its configured SSH user CA. [Native SSH docs](https://www.pomerium.com/docs/capabilities/native-ssh-access)

That means Pomerium now overlaps with Smallstep’s “developer gets short-lived SSH access” use case.

The difference is still important:

- **Pomerium SSH** is an **access mediation** feature tightly coupled to Pomerium routing and policy.
- **Smallstep SSH** is an **SSH CA / PKI** feature that can exist independently of a Pomerium access plane.

## 4. Where they are complementary, and whether you need both

They are complementary when the platform needs **both**:

- identity-aware application access and policy enforcement, and
- an internal CA for workload / service / cluster / SSH certificates.

That means:

- If the stack needs **browser-to-app auth, policy enforcement, route-level access control, and operator SSH through the same zero-trust access plane**, Pomerium is the right fit.
- If the stack needs **service mesh certs, internal ACME, cert-manager integration, pod/workload certificates, K8s service-account-based issuance, or a reusable SSH/X.509 CA**, Smallstep is still the right fit.

So do you need both?

- **Yes**, if Auth v5 needs both a **ZTNA / access proxy** and a **private PKI**.
- **No**, if the only remaining Smallstep use case was “developers need JIT SSH access,” because Pomerium now covers that credibly.

The key design question is not “can Pomerium do certs at all?” It can. The question is “can Pomerium replace an internal CA?” The answer is still **no**.

## 5. Pomerium on Kubernetes, and the Kong question

Pomerium’s Kubernetes story is now fairly complete:

- A cluster-wide **`Pomerium` CRD** holds global configuration.
- Individual protected services are defined as **Kubernetes `Ingress` resources** with `ingressClassName: pomerium`.
- TLS is required.
- Upstream mTLS can be configured with Kubernetes secrets such as `tls_client_secret` and `tls_custom_ca_secret`.
- Certificate automation in K8s is expected to come from **cert-manager** or another K8s-native solution, not Pomerium Autocert. [Global config](https://www.pomerium.com/docs/deploy/k8s/configure), [Ingress docs](https://www.pomerium.com/docs/k8s/ingress.html)

There is also Gateway API support with a `pomerium-gateway` `GatewayClass`, which matters if the platform is standardizing on Gateway API rather than legacy `Ingress`. [Gateway API docs](https://docs.pomerium.com/docs/deploy/k8s/gateway-api)

On **Kong integration**, I did **not** find a first-party, documented “Pomerium + Kong” integration in current Pomerium docs or Kong docs. That suggests the practical model is **composition**, not built-in integration. This is an inference from the available vendor docs, not an explicit vendor statement.

Practically, that means one of these patterns:

- **Pomerium in front of Kong-managed services** when the main need is human/operator access control.
- **Kong as API gateway, Pomerium for separate internal/admin/operator surfaces**.
- Avoid trying to make both be the same north-south ingress unless there is a strong reason; they solve adjacent but different problems.

## 6. Smallstep on Kubernetes

Smallstep’s Kubernetes integration story is deeper on certificate lifecycle:

- `step-issuer` integrates `step-ca` with `cert-manager`.
- cert-manager can also talk to `step-ca` through ACME.
- `autocert` injects and renews certificates directly in pods.
- `K8sSA` provisioners let workloads authenticate with service account tokens to obtain certs.
- `step-sds` pushes certificates to Envoy via SDS. [Integrations](https://smallstep.com/docs/step-ca/integrations/), [cert-manager tutorial](https://smallstep.com/docs/tutorials/kubernetes-acme-ca/)

This is exactly the workload identity / service-to-service certificate automation layer that Pomerium does not try to be.

## 7. Which tool provides Auth v5’s JIT SSH flow?

In 2026, **both can**, but in different ways.

- **Pomerium** now provides the most direct “developer requests SSH access at connection time” flow. User runs a normal SSH command, authenticates in browser, Pomerium evaluates policy, then signs and uses a short-lived SSH user certificate. If Auth v5 wants **policy-gated, proxied, zero-trust SSH access through the same access plane as web apps**, this is the strongest fit. [Native SSH docs](https://www.pomerium.com/docs/capabilities/native-ssh-access)
- **Smallstep** provides the more general-purpose CA flow. User or automation runs `step ssh certificate`, authenticates via provisioner logic such as OIDC, receives a short-lived SSH cert, and then connects to any host that trusts the Smallstep CA. If Auth v5 wants **standalone SSH PKI** independent of a Pomerium proxy layer, this is the better fit. [SSH CLI ref](https://smallstep.com/docs/step-cli/reference/ssh/certificate/), [SSH tutorial](https://smallstep.com/docs/tutorials/ssh-certificate-login/)

## Recommendation for Auth v5

If the spec currently includes both Pomerium and Smallstep, that still makes sense **only if** Smallstep is there for PKI beyond SSH: workload mTLS, cert-manager, ACME, K8s service-account issuance, Envoy/Kong-adjacent service identity, or broader SSH CA reuse.

If Smallstep was included mainly because “we need ephemeral SSH certs,” then the 2026 update is that **Pomerium can likely absorb that responsibility now**.

The cleanest current framing is:

- **Keep Pomerium** for identity-aware app and operator access.
- **Keep Smallstep only if Auth v5 truly needs an internal CA / PKI substrate.**
- **Do not keep Smallstep solely as a duplicate SSH story unless you explicitly want an independent SSH CA outside Pomerium.**

## Sources

- Pomerium docs overview: https://docs.pomerium.com/docs
- Pomerium Native SSH: https://www.pomerium.com/docs/capabilities/native-ssh-access
- Pomerium non-HTTP clients: https://www.pomerium.com/docs/capabilities/non-http
- Pomerium client docs: https://www.pomerium.com/docs/deploy/clients
- Pomerium Routes Portal: https://www.pomerium.com/docs/capabilities/routes-portal
- Pomerium certificate settings: https://www.pomerium.com/docs/reference/certificates
- Pomerium Autocert: https://www.pomerium.com/docs/reference/autocert
- Pomerium Kubernetes global config: https://www.pomerium.com/docs/deploy/k8s/configure
- Pomerium Kubernetes ingress: https://www.pomerium.com/docs/k8s/ingress.html
- Pomerium Gateway API: https://docs.pomerium.com/docs/deploy/k8s/gateway-api
- Pomerium releases: https://github.com/pomerium/pomerium/releases
- Smallstep `step-ca` overview: https://smallstep.com/docs/step-ca/
- Smallstep provisioners: https://smallstep.com/docs/step-ca/provisioners/
- Smallstep integrations: https://smallstep.com/docs/step-ca/integrations/
- Smallstep X.509 CLI reference: https://smallstep.com/docs/step-cli/reference/ca/certificate/
- Smallstep SSH CLI reference: https://smallstep.com/docs/step-cli/reference/ssh/certificate/
- Smallstep SSH certificate tutorial: https://smallstep.com/docs/tutorials/ssh-certificate-login/
- Smallstep cert-manager with internal ACME CA: https://smallstep.com/docs/tutorials/kubernetes-acme-ca/
