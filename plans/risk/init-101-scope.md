# Scope Risk — INIT-101

## Verdict
LOW

## Summary

The proposal holds the control-cluster boundary cleanly. The done-state is a
real local k3d cluster (`kubectl get nodes` against a channel-scoped
kubeconfig); every other Phase 5 concern — GitOps, secrets, app clusters,
DNS/TLS, ingress, workloads, HA, real Vultr apply — is named anti-scope with
a concrete successor INIT or successor phase. VKE artifacts are deleted
outright (no archive, no shim, no alias). The channel schema stays scoped to
cluster shape (distribution, target, k3s version, kubeconfig path, target
subfields, state backend); the only fields that touched downstream concerns
(`vultr.firewall`, `vultr.bootstrap.token`) are scoped to instance-level VM
plan surface and explicit plan-input shape respectively, not runtime
controllers. The remote VM path stays plan-only — no acceptance criterion
requires `tofu apply` against Vultr. HA is deferred with INIT-118 named.
Slice boundaries are clean: discard/schema → k3d module → VM module → template
rewrite → end-to-end proof → docs.

The only soft observation is that Section 7's named-successor list does not
enumerate every Phase 5 INIT by number (INIT-104/105/107–112/114–117 get
categorical exclusion but no INIT id). This is a documentation finish concern
at most — the semantic boundary is intact.

## Boundary findings

### F1 — Initiative-boundary drift: NONE

Section 2.1 explicitly names Flux→INIT-102, Infisical→INIT-103,
Crossplane→INIT-106 as later consumers, not INIT-101 work
(`proposal.md:81-89`). Section 7 anti-scope (`proposal.md:756-779`) excludes
Flux, Crossplane, app workloads, HA, Vultr LB, real apply, remote k3s,
remote kubeconfig fetch, DNS, cert-manager, Infisical, public ingress, SOPS
runtime, Buildkite worker, app-cluster claim/composition, VKE module/root/
schema. No section pulls in a downstream concern as a positive deliverable.

### F2 — Real local cluster requirement: TIGHT

Section 1 frames done-state as "a real local k3d cluster is up, a
channel-scoped kubeconfig is retrieved, and the harness proves
`kubectl get nodes` succeeds" (`proposal.md:51-53`). Section 2.12
harness check is explicitly the bare reachability assertion, not Flux
install or workload smoke (`proposal.md:410-415`). SLICE-101.05 anti-scope
forbids "no Flux install, no workload smoke test, no skipping cluster
creation" (`proposal.md:600-601`). The bar is `kubectl get nodes` — not
expanded.

### F3 — VKE artifact deletion: STRICT DISCARD

Section 2.2: "No `legacy/`, `archived/`, symlink, forwarding module,
deprecated alias, or dual schema reader remains. The reference copy is the
`feat/init-008-platform-bootstrap` branch and its worktree, not an active
directory in this branch." (`proposal.md:163-166`). D12 + Section 8 (Stale
material disposal, `proposal.md:792-819`) reinforce: no in-tree archive, no
backwards-compatible reader, no field alias, no forwarding module, no
"legacy channel" examples. Section 2.6 explicitly forbids preserving VKE
variables `cluster_kubernetes_version`, `node_plan`, `node_quantity`,
`ha_controlplanes`, `enable_firewall` as compatibility aliases
(`proposal.md:266-267`). Discard is clean.

### F4 — Slice-boundary clarity: CLEAN

- SLICE-101.01: schema discard + k3s channel contract (no module work).
- SLICE-101.02: k3d module + bring-up scripts + reachability harness.
- SLICE-101.03: Vultr VM module + cloud-init plan surface.
- SLICE-101.04: channel template dispatch + generated roots rewrite
  (depends on .01 and .03 — correct, since template calls VM module).
- SLICE-101.05: end-to-end local proof (depends on .02 and .04).
- SLICE-101.06: docs + INIT-102 handoff.

The .02 "first reachability" vs .05 "end-to-end verification" is layered,
not overlapping: .02 owns the mechanical bring-up surface; .05 owns the
done-state assertion against the full channel template path. Each slice has
its own anti-scope footnote and explicit deps.

### F5 — Anti-scope completeness: COMPREHENSIVE BY CATEGORY, SOFT ON INIT IDS

Named successors (`proposal.md:780-788`): INIT-102, INIT-103, INIT-106,
INIT-113, INIT-118, post-INIT-117 remote work. Categorical exclusions cover
the rest semantically (DNS, cert-manager, public ingress, SOPS, Buildkite
worker, app-cluster claim/composition).

Not enumerated by INIT number: INIT-104 (MinIO/object storage),
INIT-105 (cert-manager/step-ca/ExternalDNS), INIT-107 (cluster security
baseline), INIT-108 (container delivery), INIT-109 (Buildkite),
INIT-110 (Kong/Ingress), INIT-111 (Postgres), INIT-112 (backups),
INIT-114 (auth), INIT-115 (access policy), INIT-116 (tenant isolation),
INIT-117 (observability). Their concerns are excluded by category, so the
intent boundary is preserved; the gap is purely cosmetic. **Recommendation,
non-blocking:** Section 7 could add INIT ids next to "DNS automation",
"cert-manager", "public ingress", "Buildkite worker", etc. for symmetry with
INIT-102/103/106/113/118 already named.

### F6 — HA deferral: EXPLICIT WITH NAMED SUCCESSOR

Tradeoff #1 (`proposal.md:633-636`): "HA is explicitly deferred to INIT-118:
Remote Control Cluster HA." SLICE-101.03 anti-scope: "no embedded-etcd HA,
no Vultr load balancer" (`proposal.md:524-525`). Section 7: "No HA topology
beyond a single remote server in this initiative. No remote embedded-etcd
cluster. No Vultr load balancer or fixed remote registration endpoint."
(`proposal.md:761-763`). Named-successors line "INIT-118: Remote Control
Cluster HA, including multi-server topology and any fixed registration
endpoint." (`proposal.md:785-786`). Clean.

### F7 — No `tofu apply`: VERIFIED

Section 6 acceptance: "Missing Vultr credentials skip only the remote plan
assertion, never the local k3d proof." (`proposal.md:734-735`). Section 7:
"No real Vultr `tofu apply`. No remote k3s actually deployed. No remote
kubeconfig fetched." (`proposal.md:764-766`). SLICE-101.03 acceptance: "no
slice command applies remote resources." (`proposal.md:521`). Local cluster
bring-up comes through `infra/scripts/bring-up-local-channel.sh` calling
k3d, not via `tofu apply` (`proposal.md:363-377`). The harness uses
`tofu validate` and conditional `tofu plan`, never `tofu apply`
(`proposal.md:399-408`). Verified: zero apply commands in any acceptance
list.

### F8 — Channel schema: TIGHT TO CLUSTER SHAPE

Schema fields (Section 2.3, `proposal.md:182-202`): `schema_version`, `id`,
`parent`, `exposure`, `tenant`, `allow_ephemeral_children`,
`enabled_platforms`, `platform.provider` + provider config, `cluster.*`
(distribution, target, k3s_version, kubeconfig_path), per-target subobjects
(`k3d.*` and `vultr.*`), `state.backend`. No DNS fields, no Infisical/
secrets fields, no app-storage fields, no Flux/GitOps fields, no
observability fields.

Two potentially-suspect fields, both clean on inspection:
- `vultr.firewall`: cloud-level Vultr instance firewall (network ACL on the
  VM), required for any single-server plan surface. Distinct from
  Kubernetes NetworkPolicies/PodSecurityStandards/RBAC owned by INIT-107
  (those run inside the cluster). Belongs to VM provisioning, in scope.
- `vultr.bootstrap.token`: explicitly framed as plan input shape, not
  runtime secret flow. Tradeoff #9 (`proposal.md:663-665`): "INIT-101
  exposes the remote token as a plan input/reference shape but does not
  create a runtime secret flow. Infisical and remote apply are not in this
  initiative." Section 2.4 (`proposal.md:220-222`): "Remote values that
  would cause real mutation, such as SSH key IDs and allowed SSH CIDRs,
  are accepted only as plan inputs where OpenTofu can validate the root.
  They are not runtime stubs."

`state.backend` (Vultr Object Storage for remote channels) is INIT-008
carry-over per D11 (`proposal.md:336-353` synthesis), not a downstream
concern from another initiative. Schema stays in lane.

## Convergence statement

INIT-101's scope envelope matches its stated charter: provision a
self-managed k3s control cluster substrate, prove it with a real local k3d
deployment, and represent the remote Vultr VM contract as a plan-only
surface. Anti-scope is comprehensive by category and tied to named
successors for the load-bearing exclusions (Flux→102, Infisical→103,
Crossplane→106, workloads→113, HA→118, real remote apply→post-117). VKE
artifacts are discarded without compatibility surface area. Slice boundaries
are clean and dependency-correct. The channel schema stays scoped to
cluster shape and per-target VM plan inputs. No acceptance criterion
requires `tofu apply` against Vultr. The proposal is implementation-ready
from a scope perspective. The only refinement worth making before
hookpoint research is enumerating the remaining Phase 5 INIT ids
(104/105/107/108/109/110/111/112/114/115/116/117) alongside the categorical
anti-scope items in Section 7 for symmetry — non-blocking.
