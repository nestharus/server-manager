# Scope Risk — INIT-103

## Verdict
LOW

## Summary

INIT-103's proposal is convergent against its synthesis-bound scope on every
non-negotiable axis. The five hard bounds (runtime-secret-store-only,
real-local-Infisical-reconciliation, SOPS-bootstrap-only-with-narrow-extension,
no-helm-controller, channel-template-post-install integration) are each held
by named proposal sections, each with an explicit anti-scope mirror in §12,
and each with a slice that takes ownership in §9.

Concrete evidence: the Infisical install ships server + bundled-frontend +
chart-rendered Postgres + chart-rendered Redis + Operator + 6 CRDs + 1
sample `InfisicalSecret` + 1 target Secret — and nothing else (§6, §7, §10);
Helm is bound as render-time-only (§4) with the render script failing on
`HelmRelease`, `OCIRepository`, `helm.sh/chart`, `meta.helm.sh/release-*`,
`app.kubernetes.io/managed-by: Helm`, or unpinned image tags (§4); the SOPS
allowlist is extended by exactly one file
(`gitops/bootstrap/infisical-server-bootstrap.enc.yaml`) carrying exactly
seven bootstrap-tier keys, with Operator UA/service-token/Discord/app-DB/
MinIO/Vultr-OS/API-key shapes still rejected anywhere in SOPS (§5); the
Operator UA credential is generated post-server-startup and applied
directly via `kubectl apply` — never committed, never SOPS-encrypted (§5);
the `infisical` schema block is `additionalProperties: false` with nine
fields, all Operator/server-endpoint metadata — no MinIO, no cert-manager,
no Crossplane, no app-DB fields (§3); Postgres and Redis are explicitly
scoped to Infisical-only with INIT-111 application data plane named as
anti-scope on both workloads (§6); the `Service/infisical` is `ClusterIP`
with no Ingress, LoadBalancer, NodePort, public DNS, TLS, or UI publication
(§6); the local proof harness asserts real cluster reconciliation including
PVC persistence across Pod restart (§10); §12 names all 14 successor INITs
(INIT-104 through INIT-117 inclusive) plus the non-INIT supplementary
anti-scope items (HelmRelease, OCIRepository, remote dev install, the four
non-`InfisicalSecret` CR exercises, runtime secrets in SOPS, service-token
and Kubernetes auth, compatibility aliases).

One conscious deferral worth flagging: §7 accepts the chart-default
cluster-wide Operator RBAC (`scopedNamespaces: []`, `scopedRBAC: false`)
and routes scoped namespace delegation to INIT-116. This matches synthesis
D2/open-question resolution and is acknowledged in the §11 risk register;
it is not scope drift, but it is a deliberately broader-than-minimum surface
that successor INITs inherit.

## Boundary findings

| ID | Risk | Severity | Cite | Recommendation |
|---|---|---|---|---|
| S1 | Initiative-boundary drift to other Phase 5 INITs (cert-manager, Crossplane, ingress, app workloads, observability, MinIO, app-DB, Authentik) | LOW | §1 explicit non-scope list; §12 enumerates INIT-104–117 each with specific scope; §6 Service `ClusterIP` only with no Ingress/TLS/DNS | None — every successor INIT named with bound scope; only the sample `InfisicalSecret` proof crosses workload boundary, and it is the contract proof, not an app workload. |
| S2 | Real local reconciliation drifts toward cert-manager-shaped or app-workload-shaped manifests | LOW | §10 12 assertions: Pod Ready, PVC Bound, persistence (Pod-delete recovery), Operator Ready, UA Secret present, sample CR Ready, target Secret value, idempotency; §6 `ClusterIP` only | None — assertions are server + Postgres + Redis + Operator + sample CR + target Secret. No TLS issuance, no cert-manager CR, no Ingress reconciliation, no application Deployment beyond the proof Secret consumer pattern (and no consumer workload is authored). |
| S3 | SOPS-as-runtime regression (the INIT-009 mistake; collapsing the named-file invariant) | LOW | §5 allowlist extended by exactly one file: `gitops/bootstrap/infisical-server-bootstrap.enc.yaml`; §5 in-file key whitelist of 7 bootstrap-tier keys; §12 "No runtime secrets in SOPS"; SLICE-103.04 negative tests reject Operator UA keys in SOPS and reject any encrypted file outside `gitops/bootstrap/` | None — named-file invariant preserved; runtime-secret-shaped reject patterns from INIT-102 remain; Operator UA credential explicitly out of SOPS by design (§5); INIT-104 handoff (§13) explicitly forbids MinIO/Vultr-OS credentials in `gitops/bootstrap/` or any SOPS file. |
| S4 | Postgres/Redis reuse for application data plane | LOW | §6 Postgres "Anti-scope: INIT-111 application data Postgres, HA, external managed database, backup/restore"; §6 Redis "Anti-scope: external Redis, HA Redis, managed Redis, cache sharing"; D7 synthesis confirms distinct from INIT-111 | None — both data dependencies are named as Infisical-private with INIT-111 explicitly carved out; chart-rendered names (`postgresql`, `redis-master`) and `infisical-system` namespace boundary make accidental reuse implausible. |
| S5 | Helm-controller back-door (HelmRelease, OCIRepository, runtime chart fetch) | LOW | §4 "INIT-103 never installs `helm-controller`, never commits `HelmRelease`, and never asks Flux to fetch a chart"; §4 render script fails on `HelmRelease`/`OCIRepository`/helm ownership annotations; §8 Helm CLI "not installed into the cluster and not used during Flux reconciliation"; §12 anti-scope; SLICE-103.02 acceptance asserts no `HelmRelease`/`OCIRepository` in rendered output | None — render-time-only binding is enforced at three layers: prose, render-script invariant check, and slice acceptance. |
| S6 | Channel template extension creep (TF module reshape, schema bloat) | LOW | §3 schema block: `additionalProperties: false`, 9 fields, all Operator/server-endpoint metadata; §5 bootstrap script `bootstrap-infisical-identity.sh` is host-side step in `bring-up-local-channel.sh` (matches INIT-102 D8 post-install bash pattern); no new TF module introduced | None — `infisical` block follows INIT-102's `gitops` block shape (strict additive, required when `cluster.target == "k3d-local"`, optional for `vultr-vms`); no nested objects, no compatibility aliases (`env_slug`, `project_slug`, `service_token_secret_name` explicitly rejected per §3). |
| S7 | Anti-scope completeness — every Phase 5 INIT named | LOW | §12 enumerates INIT-104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117 — all 14 successors; plus non-INIT items (HelmRelease/helm-controller, OCIRepository, remote dev Flux, push/dynamic/generator/password/uuid CR exercises, runtime secrets in SOPS, service-token/k8s auth, compatibility aliases) | None — full coverage; INIT-104 also has positive interface contract in §13 to prevent ambiguous handoff. |
| S8 | Slice-boundary clarity — overlap or unowned files | LOW | §9 slices 103.01–07; each has Files / Acceptance / Anti-scope / Dependencies; clean linear dependency chain (01 → 02 → 03 → 04 → 05 → 06 → 07) | None — minor co-ownership exists where SLICE-103.02 and SLICE-103.03 both list `infra/scripts/render-infisical-manifests.sh` (single render entrypoint covering both charts, defensible) and SLICE-103.04 references `gitops/channels/local/infisical/server/kustomization.yaml` (defined in 02; 04 patches in the bootstrap Secret reference). Co-ownership is intentional and dependency order resolves it. |
| S9 | Operator RBAC creep — accepts cluster-wide breadth instead of scoped to `infisical-sample` | LOW | §7 explicit: "INIT-103 uses the chart default cluster-wide watch: `scopedNamespaces: []` and `scopedRBAC: false`. INIT-116 owns scoped namespace delegation"; §11 risk register acknowledges; synthesis D2 + open-question resolution leaves cluster-wide acceptable for INIT-103 | None — this is a deliberately accepted trade-off bound by synthesis, with explicit handoff to INIT-116. The CRDs are necessarily cluster-scoped (chart owns them); only the controller's watch breadth is at issue, and scoping it now would either force `scopedNamespaces: ["infisical-sample"]` (making INIT-104+ depend on schema work that belongs to INIT-116) or duplicate INIT-116's namespace-delegation model. Defer is correct, but flag for INIT-116 readiness. |
| S10 | Bootstrap chicken-and-egg — secret-zero solution sneaks runtime secrets into SOPS | LOW | §5 split: server-root keys (5 config + 2 admin bootstrap) in SOPS-allowlisted file; Operator UA credential generated post-server-startup by `bootstrap-infisical-identity.sh` and applied via `kubectl apply` — "never committed and never SOPS-encrypted" (§5); SLICE-103.04 negative test asserts UA keys in SOPS fails the lint | None — the two `INFISICAL_AUTO_BOOTSTRAP_EMAIL`/`_PASSWORD` keys live in SOPS but are bootstrap-tier (consumed by the host-side identity script for first-admin creation; chart `autoBootstrap.enabled: false` per §4 render values), not runtime secrets. UA `clientId`/`clientSecret` — the actual runtime credential the Operator uses — never enters Git in any form. Idempotency contract (§5) covers all partial-bootstrap recovery paths. |

## Convergence statement

INIT-103's proposal is convergent against its synthesis-bound scope. The
five non-negotiables (runtime-secret-store-only, real-local-Infisical
reconciliation, SOPS-bootstrap-only-with-narrow-extension, no-helm-controller,
channel-template-post-install integration) are each held by named proposal
sections, each with explicit anti-scope mirrors in §12, and each enforced
at runtime by either harness assertions in §10 or render-script invariants
in §4. All 14 successor Phase 5 INITs are named in §12 (INIT-104–117), and
the INIT-104 handoff has a positive interface contract in §13 that
explicitly forbids MinIO/Vultr-OS credentials in `gitops/bootstrap/`. The
SOPS boundary extension is the absolute minimum (one file, seven
bootstrap-tier keys) with the runtime-secret-shaped reject patterns and
named-file invariant intact. The Operator UA credential — the runtime
secret that proves the chicken-and-egg is solved without SOPS pollution —
is generated post-server-startup and applied directly via kubectl, never
committed. The `infisical` schema block is narrowly scoped
(`additionalProperties: false`, 9 Operator/server-endpoint fields, no
INIT-104/INIT-111/INIT-115 surface). The Helm CLI is bound as a render-time
tool, not a cluster runtime, with the render script failing on Helm
ownership annotations or `HelmRelease`/`OCIRepository` shapes. Postgres
and Redis are scoped to Infisical-only with INIT-111 carved out on both.
Cluster-wide Operator RBAC is accepted as a synthesis-bound deferral to
INIT-116 (S9) — flagged but not drift. No HIGH or MEDIUM findings were
raised; all ten boundary axes are LOW. Recommend proceeding to the next
risk gate.
