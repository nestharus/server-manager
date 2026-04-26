# INIT-105 Implementation

## Status

INIT-105 is implemented across seven slices:

- `SLICE-105.01`: strict `tls` and `dns` channel schema blocks, with local
  required blocks, remote contract blocks, inheritance, and alias rejection.
- `SLICE-105.02`: cert-manager `v1.20.2` raw manifests rendered from the
  upstream chart with CRDs included and no runtime Helm resources.
- `SLICE-105.03`: step-ca chart `1.30.1`, step-issuer chart `1.10.2`, and the
  generated local `StepClusterIssuer/humility-local-step-ca`.
- `SLICE-105.04`: local CoreDNS ConfigMap ownership for `*.humility.local`
  rewrites to `*.svc.cluster.local`.
- `SLICE-105.05`: remote contract-only ExternalDNS, Cloudflare token
  `InfisicalSecret`, and Let's Encrypt staging ACME `ClusterIssuer`.
- `SLICE-105.06`: sample `Certificate/humility-local-sample` and focused
  local TLS/DNS proof.
- `SLICE-105.07`: harness documentation and INIT-106 handoff notes.

## Pins

- cert-manager chart/app: `v1.20.2`
- cert-manager controller images:
  `quay.io/jetstack/cert-manager-controller:v1.20.2`,
  `quay.io/jetstack/cert-manager-cainjector:v1.20.2`,
  `quay.io/jetstack/cert-manager-webhook:v1.20.2`,
  `quay.io/jetstack/cert-manager-startupapicheck:v1.20.2`
- step-ca chart/app: chart `1.30.1`, app `0.30.2`,
  `cr.smallstep.com/smallstep/step-ca:0.30.2`
- step-ca bootstrap image:
  `cr.smallstep.com/smallstep/step-ca-bootstrap:latest@sha256:5270356cf91596afe18478eab60c6c0866b2cc62618f282d42827e58f84d6eae`
- step-issuer chart/app: chart `1.10.2`, app `0.10.2`,
  `cr.step.sm/smallstep/step-issuer:0.10.2`
- ExternalDNS chart/app: chart `1.20.0`, app `0.20.0`,
  `registry.k8s.io/external-dns/external-dns:v0.20.0`
- DNS proof image: `busybox:1.37.0`

## Local Contract

Local channel domain: `humility.local`.

Local issuer: `StepClusterIssuer/humility-local-step-ca`, backed by step-ca in
`step-ca-system`.

Sample proof certificate:

```text
namespace: cert-manager-test
name: humility-local-sample
dnsName: minio.minio-system.humility.local
secretName: humility-local-sample-tls
issuerRef: certmanager.step.sm/StepClusterIssuer/humility-local-step-ca
```

CoreDNS rewrites `*.humility.local` to `*.svc.cluster.local`, preserving the
default `cluster.local`, reverse lookup, metrics, hosts, and forwarding
behavior from k3s CoreDNS.

## Remote Contract

Remote manifests live under `gitops/contracts/remote/tls-dns/` and are not
referenced by `gitops/channels/local/`.

Cloudflare token flow:

```text
Infisical project: platform-dns
environment: dev
path: /dns/dev/
secret key: CLOUDFLARE_API_TOKEN
target Secret: external-dns-system/cloudflare-api-token
```

Remote ACME uses Let's Encrypt staging:
`https://acme-staging-v02.api.letsencrypt.org/directory`.

No real Cloudflare record, public DNS mutation, or public certificate issuance
is performed by INIT-105.

## Verification

Static harness:

```bash
bash infra/tests/validate_platform_bootstrap.sh
```

Cluster harness:

```bash
bash infra/tests/validate_platform_bootstrap.sh --cluster
```

Focused local TLS/DNS proof after a local channel is up:

```bash
KUBECONFIG=~/.kube/humility-local.yaml \
  bash infra/tests/validate_tls_dns_local.sh
```

Cluster-mode certificate proof:

```bash
KUBECONFIG=~/.kube/humility-local.yaml \
  kubectl get certificate -n cert-manager-test humility-local-sample \
    -o 'custom-columns=NAME:.metadata.name,READY:.status.conditions[?(@.type=="Ready")].status,SECRET:.spec.secretName'
```

Expected result:

```text
NAME                    READY   SECRET
humility-local-sample   True    humility-local-sample-tls
```

## Handoff To INIT-106

- Crossplane app-cluster provisioning should consume the channel `tls` and
  `dns` blocks instead of inventing new environment fields.
- App-cluster plans can rely on cert-manager and local CA semantics existing in
  the platform channel, but must define their own app-cluster issuer strategy
  if app clusters are separate Kubernetes clusters.
- Remote DNS remains config-only. INIT-106 must not turn on Cloudflare writes
  unless a later deployment runbook explicitly authorizes it.
- Cloudflare credentials belong in Infisical (`platform-dns`, `/dns/dev/`), not
  SOPS and not Terraform state.
- Ingress is still out of scope until INIT-110; INIT-106 should not depend on a
  public ingress controller being present.
- Production ACME remains out of scope. Remote manifests intentionally use the
  Let's Encrypt staging endpoint until the deployment initiatives decide the
  production cutover.

## Residual Risks

- step-ca is local-only private PKI for k3d. It is not a production CA or
  external trust anchor.
- CoreDNS local-domain rewriting proves cluster-internal naming only. Host OS
  DNS and browser resolution for `humility.local` are not configured here.
- Remote ExternalDNS and ACME manifests are contracts, not live remote
  deployment evidence.
