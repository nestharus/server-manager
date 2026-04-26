# INIT-110 Research: Kong Ingress

## Scope

INIT-110 adds the shared ingress layer for platform channels. It must install
Kong Gateway and Kong Ingress Controller from the upstream Kong Helm chart,
rendered into raw manifests, and prove a channel service is reachable through
Kong with cert-manager-issued TLS.

## Kong Install Shape

The upstream chart is `kong/kong` from `https://charts.konghq.com`. Local
research on 2026-04-26 found chart `3.2.0`, app version `3.9`, and controller
image `kong/kubernetes-ingress-controller:3.5`.

The chart supports DB-less Kong Gateway with the ingress controller enabled.
That matches this slice: Kong is an ingress dataplane, not the system of record
for application routing. Kubernetes Ingress resources and Kong CRDs remain the
configuration API.

The repository does not run helm-controller. The chart should therefore be
rendered once into `gitops/channels/local/ingress/kong/rendered/` and reviewed
as raw Kubernetes YAML. The values used for rendering must be committed beside
the output so future updates can be reproduced.

## Local Exposure

The existing local DNS contract rewrites
`<name>.<namespace>.humility.local` to Kubernetes service DNS. The required
ingress host pattern is `<service>.<channel>.humility.local`, so local channel
hosts can resolve without changing CoreDNS by creating channel-scoped
`ExternalName` services in namespace `local` that point at the Kong proxy
service.

For example:

- `minio.local.humility.local` resolves through the existing CoreDNS rewrite to
  `minio.local.svc.cluster.local`.
- `Service/local/minio` is an ExternalName alias to
  `kong-kong-proxy.kong-system.svc.cluster.local`.
- The HTTP Host/SNI remains `minio.local.humility.local`, so Kong routes the
  request to the MinIO backend Ingress.

This preserves INIT-105's local DNS model and avoids host-level `/etc/hosts`
requirements.

## TLS

Local TLS must use the INIT-105 `StepClusterIssuer` named
`humility-local-step-ca`. Because the issuer kind/group are not cert-manager's
default `ClusterIssuer`, local Ingress objects need:

- `cert-manager.io/issuer: humility-local-step-ca`
- `cert-manager.io/issuer-kind: StepClusterIssuer`
- `cert-manager.io/issuer-group: certmanager.step.sm`

Remote TLS uses ACME via the existing `letsencrypt-staging` contract and should
only need `cert-manager.io/cluster-issuer`.

## Sample Backend

MinIO is already present from INIT-104 and exposes unauthenticated health
endpoints on port `9000`. The sample Ingress can route host
`minio.local.humility.local` to `Service/minio-system/minio`, port `9000`, and
validate `GET /minio/health/ready`.

This proves ingress without adding an auth UI or a new sample app.

## Source Links

- Kong Helm chart repository: `https://charts.konghq.com`
- Kong chart source from `helm show chart kong/kong --version 3.2.0`:
  `https://github.com/Kong/charts/tree/main/charts/kong`
