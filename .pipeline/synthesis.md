# INIT-105 Phase 2 Synthesis: TLS and DNS Decisions

## Decision Records

- **D-CERT-MANAGER-INSTALL**: Render cert-manager v1.20.2 from the official OCI chart into `gitops/channels/local/tls/cert-manager/rendered/cert-manager-v1.20.2.yaml`; include CRDs and a separate namespace manifest.
- **D-STEP-CA-INSTALL**: Render smallstep step-certificates chart 1.30.1 to raw YAML in `gitops/channels/local/tls/step-ca/rendered/step-certificates-1.30.1.yaml`, with local-only service, persistent badger DB, pinned images, and ACME provisioner bootstrap hook.
- **D-LOCAL-ISSUER**: Use Step Issuer chart 1.10.2 plus an in-cluster configure Job to create `StepClusterIssuer/humility-local-step-ca` pointing at `https://step-ca.step-ca-system.svc.cluster.local`.
- **D-COREDNS-CONFIG**: Own a local CoreDNS ConfigMap that maps `*.humility.local` service-style names to `*.svc.cluster.local`; no public DNS is changed.
- **D-CHANNEL-SCHEMA-EXT**: Add top-level strict `tls` and `dns` channel blocks to source and resolved schemas; local k3d requires step-ca/CoreDNS values, remote Vultr may carry Cloudflare/ACME contract values.
- **D-EXTERNAL-DNS-CONTRACT**: Render ExternalDNS 1.20.0 Cloudflare manifests only under remote contract paths; do not include them in local Flux reconciliation.
- **D-ACME-CONTRACT**: Add `ClusterIssuer/letsencrypt-staging` using the Let's Encrypt staging ACME endpoint and Cloudflare DNS-01 token Secret; config-only in INIT-105.
- **D-CF-CREDENTIAL-FLOW**: Cloudflare API token is stored under Infisical project `platform-dns`, path `/dns/dev/`, materialized to `Secret/cloudflare-api-token` in `external-dns-system`; never SOPS.
- **D-LOCAL-CONTRACT**: Harness proves cert-manager deployments available, step-ca ready, Step Issuer ready, sample Certificate Ready=True, and `minio.minio-system.humility.local` resolves inside cluster.
- **D-VERSION-PINS**: Pin cert-manager v1.20.2, step-ca 0.30.2/chart 1.30.1, step-issuer 0.10.2/chart 1.10.2, ExternalDNS 0.20.0/chart 1.20.0, busybox 1.37.0 for DNS proof.

## Consequences

- **Local first**: A developer can run the local cluster and observe a real private certificate issued through step-ca-backed cert-manager flow.
- **Remote restrained**: Cloudflare and ACME remote files are inspectable contracts but cannot mutate public DNS from INIT-105.
- **No compatibility**: There are no aliases like `certs`, `certificate`, `dns_provider`, or `cloudflare_token`; schema fields are canonical.
- **Handoff**: INIT-106 receives a known TLS/DNS substrate but not ingress, public records, or production ACME.

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

