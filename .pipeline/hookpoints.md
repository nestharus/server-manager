# INIT-105 Phase 5 Hookpoints

## Reuse Points

- **Flux local overlay**: Reuse `gitops/channels/local/kustomization.yaml` as the only local apply entrypoint.
- **Rendered chart pattern**: Reuse INIT-103 rendered chart layout: `render-values.yaml` beside `rendered/<chart-version>.yaml`.
- **Channel resolver**: Reuse parent inheritance and strict JSON Schema validation for new `tls` and `dns` blocks.
- **Bootstrap harness**: Reuse pass/fail shell harness style and `--cluster` mode gating.
- **Infisical boundary**: Reuse INIT-103 `InfisicalSecret` shape for Cloudflare token contract, but do not apply it locally.

## Collisions

- **CoreDNS ownership**: The k3s CoreDNS ConfigMap already exists; INIT-105 replaces it with a controlled local Corefile and must keep default Kubernetes DNS behavior.
- **CRD timing**: cert-manager and step-issuer CRDs may be applied in the same Flux run as CRs; retry semantics handle initial discovery lag.
- **StepIssuer necessity**: A step-ca-backed cert-manager Certificate needs Step Issuer; built-in ACME would pull ingress or DNS01 machinery into local scope.

## Blockers

- **None for local**: Docker/k3d are available and no Discord-visible action is required.
- **Remote credentials**: Cloudflare token is not needed for INIT-105 because remote manifests are contract-only.

## Delete/Do Not Build

- **No helm-controller**: No HelmRelease or runtime chart source objects.
- **No public DNS**: No Cloudflare API calls or records.
- **No ingress**: No HTTP-01 solver or ingress class.

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
