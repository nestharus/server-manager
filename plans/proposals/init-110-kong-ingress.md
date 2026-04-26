# INIT-110 Proposal: Ingress via Kong

## 1. Summary

INIT-110 adds Kong Gateway and Kong Ingress Controller as the platform ingress
layer. It extends the channel schema with an optional `ingress` block, renders
the upstream Kong chart into raw manifests, adds a default MinIO Ingress with
cert-manager TLS, and ships a local validation harness.

The work is six implementation slices:

1. Pipeline artifacts.
2. Channel ingress contract.
3. Kong chart render as raw manifests.
4. Sample service ingress, DNS alias, TLS contract, and network policy.
5. Validation harness and static tests.
6. Handoff and review artifacts.

## 2. Architecture

Kong runs in `kong-system` as a DB-less Gateway with KIC enabled. Kubernetes
Ingress remains the routing API. The chart render includes Kong CRDs so later
policy initiatives can add Kong CRs without introducing a second install path.

Local hostnames use `<service>.local.humility.local`. The existing CoreDNS
rewrite maps these names to Kubernetes service names. INIT-110 adds namespace
`local` and `ExternalName` aliases to the Kong proxy service so the hostnames
resolve to Kong while preserving the original Host header for routing.

Remote hostnames use `<service>.<channel>.humility.gg`. Remote DNS is expected
to be handled by the INIT-105 external-dns contract and the remote ACME issuer.

## 3. Contracts

The channel `ingress` block contains:

- `provider`
- `gateway_namespace`
- `chart_name`
- `chart_version`
- `gateway_image`
- `controller_image`
- `ingress_class_name`
- `proxy_service_name`
- `proxy_service_type`
- `local_dns_namespace`
- `local_domain`
- `remote_domain`
- `local_cluster_issuer_name`
- `remote_cluster_issuer_name`
- `default_service`

`default_service` contains service name, namespace, port, local host, remote
host, TLS secret, and proof path.

## 4. Anti-Scope

INIT-110 does not add authentication, rate limiting, plugin policy, OAuth/OIDC,
Kong Manager exposure, Kong Enterprise, production ACME issuer promotion, or a
plugin marketplace.

## 5. Risk Notes

The main shortcut risk is hand-authoring Kong manifests and calling them a chart
render. The proposal avoids that by committing Helm values beside rendered
upstream output.

The second risk is DNS ambiguity. The proposal reuses INIT-105's local CoreDNS
rewrite and adds explicit local aliases rather than requiring host-machine DNS
changes.

The third risk is a fake proof. The harness waits for Kong, the sample
Certificate, DNS resolution, and an HTTPS curl through Kong to MinIO's health
endpoint.

## 6. Acceptance

- local and dev channels resolve with `ingress`;
- `kubectl kustomize gitops/channels/local/ingress` succeeds;
- `kubectl kustomize gitops/channels/local` succeeds;
- static harness passes without a cluster;
- runtime harness proves Kong Pod up, cert Ready=True, DNS resolution, and
  HTTPS curl through Kong returns a successful MinIO health response;
- CodeRabbit and PR review artifacts are clean or residual gaps are recorded.
