# Scope Risk — INIT-102

## Verdict
LOW

## Summary

INIT-102's proposal is convergent against its synthesis-bound scope on every
non-negotiable axis. The five hard bounds (GitOps-substrate-only,
real-local-reconciliation, SOPS-bootstrap-only, in-cluster-git-daemon,
post-install-script integration) are each held by named proposal sections,
each with an explicit anti-scope mirror in §14, and each with a slice that
takes ownership in §9.

Concrete evidence: the Flux install ships only `source-controller` +
`kustomize-controller` with the four omitted controllers individually
justified against their downstream INITs (§7); SOPS encrypts exactly one
sentinel file (§6) with an `encrypted_regex: ^(data|stringData)$` scope and
a failing harness lint that scans `gitops/**/*.enc.yaml` and rejects
runtime-secret-shaped keys (§6, §12); the local source is the in-cluster
`git daemon` Deployment + ClusterIP, and the schema's `source_kind` is
`enum: ["git"]` so OCI/MinIO are syntactically rejected (§3, §5); the
channel-template integration is `install-flux-for-channel.sh` and a
would-be `infra/modules/platform-flux/` is explicitly rejected with a
named reason (§4); the new `gitops` schema block is `additionalProperties:
false` with nine fields, all of which are Flux source or SOPS bootstrap
metadata — no Infisical, no cert-manager, no runtime-secret-provider
fields (§3, synthesis D7); the local-proof harness asserts real cluster
reconciliation rather than render checks (§12). Slice boundaries (§9)
form a clean linear dependency chain: 102.01 toolchain → 102.02 layout
+ Flux lockfile → 102.03 SOPS bootstrap → 102.04 schema + render →
102.05 Git server + post-install → 102.06 harness + docs, with no
file-surface overlap.

§14 names all 15 successor INITs (INIT-103 through INIT-117 inclusive,
including INIT-107 cluster security baseline at line 1006) plus the
non-INIT supplementary anti-scope items (remote dev Flux, `flux bootstrap`,
GitHub round-trip, OCIRepository/MinIO sources, HelmRelease, runtime
secrets in SOPS, stale `k8s/` retention). The `dev` channel deliberately
omits the `gitops` block; the resolved schema makes `gitops` required
only when `cluster.target=k3d-local`, locking single-cluster posture at
the schema layer.

No HIGH-risk bleeds (Infisical, runtime secrets, app workloads,
app-cluster, Crossplane, cert-manager, image automation,
notification-controller, OCI/MinIO sources) and no MEDIUM-risk
ambiguities were detected.

## Boundary findings
| ID | Risk | Severity | Cite | Recommendation |
|---|---|---|---|---|
| S1 | Initiative-boundary drift to other Flux controllers (helm/notification/image) | LOW | §7 component table; §2 resource-count table (22 resources, 2 Deployments); §14 anti-scope | None — each excluded controller named with downstream INIT; SLICE-102.02 acceptance asserts `rg` finds no helm/notification/image controller Deployment names. |
| S2 | Real local reconciliation pulls in cert-manager- or workload-shaped manifests | LOW | §6 sentinel Secret content (`channel: local`, `sentinel: sops-local-ready`); §12 harness assertions; `gitops/bases/gitops-sentinel/` layout in §2 | None — sentinel surface is `Namespace/humility-gitops-sentinel` + `ConfigMap/gitops-sentinel` + bootstrap `Secret/gitops-sops-sentinel`. No app workload, no TLS/cert-manager, no ingress. |
| S3 | SOPS-as-runtime regression (the INIT-009 mistake) | LOW | §6 single encrypted file; §6 boundary lint; §14 "Runtime secrets in SOPS" anti-scope; synthesis D5 | None — exactly one `*.enc.yaml` allowlisted; `encrypted_regex: ^(data\|stringData)$`; failing lint rejects `infisical*`, `discord*token`, db passwords, and any encrypted file outside the allowlist (addresses prior SC-006). |
| S4 | Local-source alternative leak (gitea, OCI registry, hostPath) | LOW | §5 in-cluster `git daemon` Deployment + ClusterIP; §3 `source_kind: enum: ["git"]`; §14 "OCIRepository or MinIO bucket-watched Flux sources" anti-scope | None — only `git daemon` mechanism specified; OCI rejected at schema-validation time per synthesis D7 open-question resolution. |
| S5 | New TF module overlapping INIT-101's channel template | LOW | §4 "Rejected TF Module Shape" table explicitly rejects `infra/modules/platform-flux/`; synthesis D8 | None — post-install script `install-flux-for-channel.sh` is the only integration point; INIT-101's TF module surface is not reshaped, only `bring-up-local-channel.sh` is extended to call the new script. |
| S6 | Anti-scope completeness — every Phase 5 INIT named | LOW | §14 enumerates INIT-103, 104, 105, 106, 107 (line 1006), 108, 109, 110, 111, 112, 113, 114, 115, 116, 117 | None — INIT-107 cluster security baseline is now explicitly named ("addresses S6" notation in proposal indicates this gap was closed during prior pass). |
| S7 | Slice boundaries unclear or overlapping | LOW | §9 slices 102.01–06; each has Files / Acceptance / Anti-scope / Dependencies | None — 102.01 toolchain only; 102.02 layout + Flux lockfile (no SOPS, no schema); 102.03 SOPS bootstrap sentinel; 102.04 schema + render; 102.05 Git server + post-install; 102.06 harness + docs. No file overlap; clean linear dependency chain. |
| S8 | Flux component subset drift (D2) | LOW | §7 component table; §2 generating command `--components=source-controller,kustomize-controller`; §11 reproducibility lockfile | None — selector pinned at the `flux install --export` invocation; CRD set listed and acknowledged as broader-than-used because Flux source-controller install owns all source CRDs (no resource leak, just CRD breadth — used kinds are `GitRepository` + `Kustomization` only). |
| S9 | Schema creep into downstream-INIT concerns | LOW | §3 schema fields; `additionalProperties: false`; synthesis D7 boundary clause "No runtime secret provider fields" | None — 9 fields total: `source_kind` (enum `git`), `git_url`, `git_ref`, `path` (regex-bounded to `./gitops/channels/<id>`), `interval_source`, `interval_kustomization`, `flux_version`, `sops_age_secret_name`, `decryption_secret_namespace`. No Infisical, no cert-manager, no Crossplane fields. |
| S10 | HA / multi-cluster posture creep | LOW | §1 "does not install Flux on the remote `dev` Vultr-VM channel"; §3 `dev.yaml` deliberately omits `gitops` block, conditional schema makes `gitops` required only when `cluster.target=k3d-local`; §13 "Local k3d channel only"; §14 "Remote `dev` Flux installation" anti-scope | None — single-channel, single-cluster posture is enforced at three layers: prose, schema conditional, and anti-scope. Absence of `gitops/channels/dev/` overlay confirms it. |

## Convergence statement

INIT-102's proposal is convergent against its synthesis-bound scope.
The five non-negotiables (GitOps-substrate-only, real-local-reconciliation,
SOPS-bootstrap-only, in-cluster-git-daemon, post-install-script
integration) are each held by named proposal sections, each with explicit
anti-scope mirrors in §14, and each enforced at runtime by harness
assertions in §12. All 15 successor Phase 5 INITs are named in §14,
including INIT-107 (cluster security baseline) which was added during
a prior risk pass. No HIGH or MEDIUM findings were raised; all ten
boundary axes are LOW. The `gitops` schema block is narrowly scoped
(`additionalProperties: false`, 9 Flux/SOPS-bootstrap fields, no
runtime-secret-provider surface), the Flux component subset is pinned
to source + kustomize controllers with selector and acceptance assertion,
the SOPS boundary is enforced by content lint not just review convention,
and the channel-template integration stays in script land — not OpenTofu.
Recommend proceeding to the next risk gate.
