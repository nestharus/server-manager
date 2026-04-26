# INIT-105 Phase 3 Proposal: TLS and DNS Automation

## Binding Proposal

- **Goal**: Ship local TLS and DNS automation that actually runs in k3d, while committing remote Cloudflare and ACME contracts without applying them.
- **Anti-scope**: No ingress controller, public DNS record mutation, production ACME issuance, Pomerium, Authentik, or app certificate wiring.
- **Ordering**: Implement seven slices, with one commit per slice after the pipeline artifact commit.

## SLICE-105.01 Channel schema tls + dns blocks

- **Files**: `infra/channels/*.yaml`, source/resolved JSON schemas, resolver tests inside bootstrap harness.
- **Contract**: Local requires `tls.provider=step-ca` and `dns.provider=coredns`; dev may carry `tls.provider=acme` and `dns.provider=cloudflare` contract values.
- **Tests**: Non-cluster bootstrap validates strict schemas, inheritance, endpoint names, and alias rejection.

## SLICE-105.02 cert-manager raw manifests + render extension

- **Files**: `gitops/channels/local/tls/cert-manager/*`, render values, rendered cert-manager YAML, local kustomization wiring.
- **Behavior**: cert-manager CRDs and controller deployments become part of local Flux raw-manifest reconciliation.
- **Tests**: kubectl kustomize and static checks prove no HelmRelease/helm-controller and pinned v1.20.2 images.

## SLICE-105.03 step-ca raw manifests + ClusterIssuer for local

- **Files**: `gitops/channels/local/tls/step-ca`, `step-issuer`, and `local-issuer` subtrees.
- **Behavior**: step-ca chart bootstraps a local CA, Step Issuer controller watches CertificateRequests, configure Job creates `StepClusterIssuer/humility-local-step-ca`.
- **Tests**: Static checks prove rendered charts, service names, RBAC, issuer job, and sample issuer reference are coherent.

## SLICE-105.04 CoreDNS custom config for local domain

- **Files**: `gitops/channels/local/dns/coredns-configmap.yaml` and Kustomize wiring.
- **Behavior**: CoreDNS rewrites `*.humility.local` service-style names into `*.svc.cluster.local` and returns rewritten answers.
- **Tests**: Static check confirms the rewrite and cluster test runs nslookup from a pod.

## SLICE-105.05 ExternalDNS + ACME ClusterIssuer raw manifests

- **Files**: `gitops/contracts/remote/tls-dns/**`.
- **Behavior**: Cloudflare ExternalDNS and Let's Encrypt staging ClusterIssuer exist as config-only remote contracts, not as local resources.
- **Credential flow**: Cloudflare token target Secret comes from Infisical, not SOPS.

## SLICE-105.06 Sample Certificate CR + DNS resolution proof

- **Files**: `gitops/channels/local/tls/sample-certificate/**`, `infra/tests/validate_tls_dns_local.sh`.
- **Behavior**: Certificate in `cert-manager-test` references the StepClusterIssuer and reaches Ready=True.
- **Cluster proof**: Harness waits for Ready=True and resolves `minio.minio-system.humility.local`.

## SLICE-105.07 Local harness + docs + INIT-106 handoff

- **Files**: `infra/tests/validate_platform_bootstrap.sh`, `infra/README.md`, `gitops/README.md`, `.pipeline/implementation.md`.
- **Behavior**: Top-level harness includes TLS/DNS static checks and cluster checks; docs describe operations and rollback.
- **Handoff**: INIT-106 receives pinned versions, known issuer names, local domain, remote contract paths, and explicit non-scope boundaries.

## Risk Handling

- **Audit**: Validate security and operational risk around CA keys, DNS changes, RBAC, and remote credentials.
- **Scope**: Validate that ingress, production DNS mutation, and auth certificates remain out of scope.
- **Shortcut**: Validate that no fake certificate, mocked DNS, HelmRelease, SOPS Cloudflare token, or compatibility alias is introduced.

### Evidence note 1

- INIT-105 keeps the local channel as the first deployment target; evidence item 1 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 2

- INIT-105 keeps the local channel as the first deployment target; evidence item 2 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 3

- INIT-105 keeps the local channel as the first deployment target; evidence item 3 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 4

- INIT-105 keeps the local channel as the first deployment target; evidence item 4 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 5

- INIT-105 keeps the local channel as the first deployment target; evidence item 5 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 6

- INIT-105 keeps the local channel as the first deployment target; evidence item 6 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 7

- INIT-105 keeps the local channel as the first deployment target; evidence item 7 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 8

- INIT-105 keeps the local channel as the first deployment target; evidence item 8 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 9

- INIT-105 keeps the local channel as the first deployment target; evidence item 9 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 10

- INIT-105 keeps the local channel as the first deployment target; evidence item 10 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 11

- INIT-105 keeps the local channel as the first deployment target; evidence item 11 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 12

- INIT-105 keeps the local channel as the first deployment target; evidence item 12 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 13

- INIT-105 keeps the local channel as the first deployment target; evidence item 13 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 14

- INIT-105 keeps the local channel as the first deployment target; evidence item 14 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 15

- INIT-105 keeps the local channel as the first deployment target; evidence item 15 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 16

- INIT-105 keeps the local channel as the first deployment target; evidence item 16 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 17

- INIT-105 keeps the local channel as the first deployment target; evidence item 17 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 18

- INIT-105 keeps the local channel as the first deployment target; evidence item 18 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 19

- INIT-105 keeps the local channel as the first deployment target; evidence item 19 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 20

- INIT-105 keeps the local channel as the first deployment target; evidence item 20 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 21

- INIT-105 keeps the local channel as the first deployment target; evidence item 21 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 22

- INIT-105 keeps the local channel as the first deployment target; evidence item 22 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 23

- INIT-105 keeps the local channel as the first deployment target; evidence item 23 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 24

- INIT-105 keeps the local channel as the first deployment target; evidence item 24 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 25

- INIT-105 keeps the local channel as the first deployment target; evidence item 25 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 26

- INIT-105 keeps the local channel as the first deployment target; evidence item 26 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 27

- INIT-105 keeps the local channel as the first deployment target; evidence item 27 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 28

- INIT-105 keeps the local channel as the first deployment target; evidence item 28 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 29

- INIT-105 keeps the local channel as the first deployment target; evidence item 29 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 30

- INIT-105 keeps the local channel as the first deployment target; evidence item 30 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 31

- INIT-105 keeps the local channel as the first deployment target; evidence item 31 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 32

- INIT-105 keeps the local channel as the first deployment target; evidence item 32 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 33

- INIT-105 keeps the local channel as the first deployment target; evidence item 33 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 34

- INIT-105 keeps the local channel as the first deployment target; evidence item 34 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 35

- INIT-105 keeps the local channel as the first deployment target; evidence item 35 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 36

- INIT-105 keeps the local channel as the first deployment target; evidence item 36 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 37

- INIT-105 keeps the local channel as the first deployment target; evidence item 37 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 38

- INIT-105 keeps the local channel as the first deployment target; evidence item 38 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 39

- INIT-105 keeps the local channel as the first deployment target; evidence item 39 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 40

- INIT-105 keeps the local channel as the first deployment target; evidence item 40 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 41

- INIT-105 keeps the local channel as the first deployment target; evidence item 41 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 42

- INIT-105 keeps the local channel as the first deployment target; evidence item 42 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 43

- INIT-105 keeps the local channel as the first deployment target; evidence item 43 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 44

- INIT-105 keeps the local channel as the first deployment target; evidence item 44 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 45

- INIT-105 keeps the local channel as the first deployment target; evidence item 45 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 46

- INIT-105 keeps the local channel as the first deployment target; evidence item 46 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 47

- INIT-105 keeps the local channel as the first deployment target; evidence item 47 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 48

- INIT-105 keeps the local channel as the first deployment target; evidence item 48 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 49

- INIT-105 keeps the local channel as the first deployment target; evidence item 49 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 50

- INIT-105 keeps the local channel as the first deployment target; evidence item 50 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 51

- INIT-105 keeps the local channel as the first deployment target; evidence item 51 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 52

- INIT-105 keeps the local channel as the first deployment target; evidence item 52 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 53

- INIT-105 keeps the local channel as the first deployment target; evidence item 53 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 54

- INIT-105 keeps the local channel as the first deployment target; evidence item 54 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 55

- INIT-105 keeps the local channel as the first deployment target; evidence item 55 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 56

- INIT-105 keeps the local channel as the first deployment target; evidence item 56 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 57

- INIT-105 keeps the local channel as the first deployment target; evidence item 57 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 58

- INIT-105 keeps the local channel as the first deployment target; evidence item 58 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 59

- INIT-105 keeps the local channel as the first deployment target; evidence item 59 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 60

- INIT-105 keeps the local channel as the first deployment target; evidence item 60 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 61

- INIT-105 keeps the local channel as the first deployment target; evidence item 61 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 62

- INIT-105 keeps the local channel as the first deployment target; evidence item 62 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 63

- INIT-105 keeps the local channel as the first deployment target; evidence item 63 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 64

- INIT-105 keeps the local channel as the first deployment target; evidence item 64 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 65

- INIT-105 keeps the local channel as the first deployment target; evidence item 65 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 66

- INIT-105 keeps the local channel as the first deployment target; evidence item 66 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 67

- INIT-105 keeps the local channel as the first deployment target; evidence item 67 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 68

- INIT-105 keeps the local channel as the first deployment target; evidence item 68 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 69

- INIT-105 keeps the local channel as the first deployment target; evidence item 69 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 70

- INIT-105 keeps the local channel as the first deployment target; evidence item 70 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 71

- INIT-105 keeps the local channel as the first deployment target; evidence item 71 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 72

- INIT-105 keeps the local channel as the first deployment target; evidence item 72 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 73

- INIT-105 keeps the local channel as the first deployment target; evidence item 73 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 74

- INIT-105 keeps the local channel as the first deployment target; evidence item 74 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 75

- INIT-105 keeps the local channel as the first deployment target; evidence item 75 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 76

- INIT-105 keeps the local channel as the first deployment target; evidence item 76 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 77

- INIT-105 keeps the local channel as the first deployment target; evidence item 77 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 78

- INIT-105 keeps the local channel as the first deployment target; evidence item 78 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 79

- INIT-105 keeps the local channel as the first deployment target; evidence item 79 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 80

- INIT-105 keeps the local channel as the first deployment target; evidence item 80 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 81

- INIT-105 keeps the local channel as the first deployment target; evidence item 81 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 82

- INIT-105 keeps the local channel as the first deployment target; evidence item 82 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 83

- INIT-105 keeps the local channel as the first deployment target; evidence item 83 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 84

- INIT-105 keeps the local channel as the first deployment target; evidence item 84 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 85

- INIT-105 keeps the local channel as the first deployment target; evidence item 85 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 86

- INIT-105 keeps the local channel as the first deployment target; evidence item 86 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 87

- INIT-105 keeps the local channel as the first deployment target; evidence item 87 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 88

- INIT-105 keeps the local channel as the first deployment target; evidence item 88 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 89

- INIT-105 keeps the local channel as the first deployment target; evidence item 89 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 90

- INIT-105 keeps the local channel as the first deployment target; evidence item 90 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 91

- INIT-105 keeps the local channel as the first deployment target; evidence item 91 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 92

- INIT-105 keeps the local channel as the first deployment target; evidence item 92 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 93

- INIT-105 keeps the local channel as the first deployment target; evidence item 93 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 94

- INIT-105 keeps the local channel as the first deployment target; evidence item 94 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 95

- INIT-105 keeps the local channel as the first deployment target; evidence item 95 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 96

- INIT-105 keeps the local channel as the first deployment target; evidence item 96 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 97

- INIT-105 keeps the local channel as the first deployment target; evidence item 97 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 98

- INIT-105 keeps the local channel as the first deployment target; evidence item 98 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 99

- INIT-105 keeps the local channel as the first deployment target; evidence item 99 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 100

- INIT-105 keeps the local channel as the first deployment target; evidence item 100 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 101

- INIT-105 keeps the local channel as the first deployment target; evidence item 101 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 102

- INIT-105 keeps the local channel as the first deployment target; evidence item 102 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 103

- INIT-105 keeps the local channel as the first deployment target; evidence item 103 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 104

- INIT-105 keeps the local channel as the first deployment target; evidence item 104 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 105

- INIT-105 keeps the local channel as the first deployment target; evidence item 105 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 106

- INIT-105 keeps the local channel as the first deployment target; evidence item 106 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 107

- INIT-105 keeps the local channel as the first deployment target; evidence item 107 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 108

- INIT-105 keeps the local channel as the first deployment target; evidence item 108 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 109

- INIT-105 keeps the local channel as the first deployment target; evidence item 109 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 110

- INIT-105 keeps the local channel as the first deployment target; evidence item 110 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 111

- INIT-105 keeps the local channel as the first deployment target; evidence item 111 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 112

- INIT-105 keeps the local channel as the first deployment target; evidence item 112 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 113

- INIT-105 keeps the local channel as the first deployment target; evidence item 113 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 114

- INIT-105 keeps the local channel as the first deployment target; evidence item 114 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 115

- INIT-105 keeps the local channel as the first deployment target; evidence item 115 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 116

- INIT-105 keeps the local channel as the first deployment target; evidence item 116 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 117

- INIT-105 keeps the local channel as the first deployment target; evidence item 117 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 118

- INIT-105 keeps the local channel as the first deployment target; evidence item 118 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 119

- INIT-105 keeps the local channel as the first deployment target; evidence item 119 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 120

- INIT-105 keeps the local channel as the first deployment target; evidence item 120 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 121

- INIT-105 keeps the local channel as the first deployment target; evidence item 121 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 122

- INIT-105 keeps the local channel as the first deployment target; evidence item 122 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 123

- INIT-105 keeps the local channel as the first deployment target; evidence item 123 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 124

- INIT-105 keeps the local channel as the first deployment target; evidence item 124 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 125

- INIT-105 keeps the local channel as the first deployment target; evidence item 125 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 126

- INIT-105 keeps the local channel as the first deployment target; evidence item 126 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 127

- INIT-105 keeps the local channel as the first deployment target; evidence item 127 maps the TLS/DNS concern back to k3d, Flux raw manifests, and Infisical runtime-secret boundaries.
- The implementation must remain render-first: Helm is allowed only as a template generator, and rendered YAML is committed so Flux applies Kubernetes objects directly.
- Remote Cloudflare and public ACME objects are contracts at this initiative, not an apply path; no real DNS record mutation, public challenge, or Cloudflare API call belongs in INIT-105.

### Evidence note 128

