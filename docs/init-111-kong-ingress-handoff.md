# INIT-111 Handoff: Auth and Edge Policy

INIT-110 established Kong as the platform ingress layer.

Stable surfaces:

- Channel ingress contract lives in `infra/channels/{local,dev}.yaml`.
- Schema support lives in `infra/schemas/platform-channel*.schema.json`.
- Local Kong raw manifests live under `gitops/channels/local/ingress/kong`.
- The upstream render is from chart `kong/kong` `3.2.0`, Gateway image
  `kong:3.9`, KIC image `kong/kubernetes-ingress-controller:3.5`.
- The ingress class is `kong`.
- The Kong deployment is `kong-kong`, and the proxy service is
  `kong-kong-proxy`.
- Local host pattern is `<service>.local.humility.local`.
- Remote host pattern is `<service>.<channel>.humility.gg`.
- The sample route is `https://minio.local.humility.local/minio/health/ready`.
- Local TLS uses `StepClusterIssuer/humility-local-step-ca` with
  `cert-manager.io/issuer`, `cert-manager.io/issuer-kind`, and
  `cert-manager.io/issuer-group` annotations.
- Validation lives at `infra/tests/validate_kong_ingress_local.sh`.

INIT-111 can build on this by adding auth at the edge. Recommended boundaries:

- keep Kong installation and ingress host contracts owned by INIT-110;
- add authentication as explicit Kong policy resources or auth service routes;
- do not expose Kong Manager;
- do not add rate limiting or marketplace plugin scope unless the INIT-111
  proposal explicitly includes it;
- keep sample unauthenticated health proof available as a substrate smoke test.

Local proof from INIT-110:

```text
PASS: Kong Deployment Available
PASS: Certificate/minio-local-ingress-tls Ready=True and TLS Secret exists
PASS: cluster DNS resolves minio.local.humility.local
PASS: curl https://minio.local.humility.local/minio/health/ready through Kong succeeded
RESULT: pass=12 fail=0 skip=0
```
