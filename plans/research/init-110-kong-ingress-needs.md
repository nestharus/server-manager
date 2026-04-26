# INIT-110 Synthesis: User Needs and Decisions

## Decisions

- D-KONG-CHART: render `kong/kong` chart `3.2.0` into raw GitOps manifests.
- D-KONG-IMAGES: pin Gateway `kong:3.9` and KIC
  `kong/kubernetes-ingress-controller:3.5`.
- D-NAMESPACE: install Kong into namespace `kong-system`.
- D-INGRESS-CLASS: use ingress class `kong`.
- D-LOCAL-HOSTS: use `<service>.local.humility.local`.
- D-REMOTE-HOSTS: use `<service>.<channel>.humility.gg`.
- D-LOCAL-TLS: issue local ingress certs with INIT-105
  `StepClusterIssuer/humility-local-step-ca`.
- D-REMOTE-TLS: use the existing ACME ClusterIssuer contract for remote
  channels.
- D-SAMPLE: expose MinIO health through `minio.local.humility.local`.
- D-NO-POLICIES: auth, rate limiting, and plugin marketplace remain out of
  scope for INIT-110.

## Humility Context

The platform now has local k3d, GitOps, Infisical, object storage, TLS/DNS,
app-cluster provisioning, security baseline, registry, and CI/CD. Ingress is
the next shared boundary. It needs to be channel-aware and reproducible, but it
should not pull auth or policy concerns forward from later initiatives.

The local proof must be stronger than render-only. A valid local run means the
Kong Pod is up, a sample Ingress is programmed, cert-manager issues the host
certificate, channel DNS resolves to Kong, and curl through Kong reaches the
backend.

## Gaps

Remote DNS still points at `humility.example` in INIT-105's dev contract. The
binding INIT-110 host pattern is `humility.gg`; this slice updates the channel
contract to the target domain but does not provision public DNS credentials or
ACME production issuers.
