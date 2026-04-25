# INIT-009 Phase 3 Proposal: GitOps Substrate

## Binding sources

- `.pipeline/research.md` - Phase 1 evidence over existing GitOps,
  Kustomize, Flux, SOPS+age, and local verification state.
- `.pipeline/synthesis.md` - D1-D12, stale-material disposition, and six
  candidate slices.
- `worktrees/init-008-platform-bootstrap/.pipeline/proposal.md` - final
  channel-registry and control-cluster substrate contract.
- `worktrees/init-008-platform-bootstrap/infra/channels/dev.yaml` - current
  `dev` platform channel definition.
- `memory/channel-template-pattern.md` - channel/template inheritance is the
  binding Phase 5 shape.
- `memory/local-only-verification.md` - Phase 5 done-ness is local-only.
- `memory/two-tier-cluster-architecture.md` - control-cluster versus
  application-cluster responsibility split.
- `product-strategy/tickets/PHASE_5_INDEX.md` - current 13-initiative Phase 5
  dependency order.
- `product-strategy/tickets/INIT-001.md` - initiative ticket shape.
- `~/ai/conventions/no-backwards-compatibility.md` - old shape is deleted, not
  preserved.
- `~/ai/conventions/no-deferred-stubs.md` - placeholder surfaces must be
  explicitly authorized by scheduled follow-up initiatives.

This proposal is bound to synthesis decisions D1-D12 and to the user's
2026-04-25 answers:

- Q1: local cluster is `kind`.
- Q2: the existing `k8s/` tree is deleted entirely.
- Q3: Flux source is this `server-manager` repository, with active manifests
  under root-level `gitops/`.
- Q4: SOPS age recipients are per-channel.
- Q5: INIT-009 includes executable toolchain preinstall, not README-only
  prerequisites.

---

## 1. Executive summary

INIT-009 establishes the GitOps substrate for the control cluster only. It
installs and self-manages Flux CD on the control cluster, replaces the stale
environment-shaped `k8s/` tree with a root-level `gitops/` tree, defines a
channel-aligned Kustomize layout, adds a SOPS+age workflow with per-channel
recipients, and ships a kind-based verification harness. This closes D1, D2,
D3, D4, D5, D6, D7, D8, D9, D10, D11, and D12 as a single substrate contract:
Flux reconciles the `dev` control-cluster channel from this repo, and local
kind verification proves that contract without touching Vultr.

INIT-009 is the gate that unlocks INIT-017, INIT-018, and INIT-019. The
control cluster hosts Flux and later hosts Crossplane, cert-manager,
ExternalDNS, and the cluster security baseline. INIT-009 creates the GitOps
paths and reconciliation contract those later initiatives populate. It does
not install Crossplane, cert-manager, ExternalDNS, or security policies beyond
empty, documented handoff bases. It does not reconcile application workloads.
Application-cluster Flux instances are delivered by Crossplane compositions in
INIT-017, not by this initiative.

The proposal deliberately rejects the old `dev/staging/production` GitOps
shape. `dev` remains the active Phase 5 channel because INIT-008's `dev`
channel is the control cluster, but the concept is now a channel id, not a
hard environment tier. Kustomize inheritance maps to channels through shared
bases and per-channel overlays. The legacy `k8s/` tree and old
environment-triad tests are removed rather than wrapped, aliased, or kept as
historical live inputs.

Local verification is the completion surface. The implementation must provide
tool installation, render checks, SOPS decrypt checks, kind bootstrap, Flux
controller installation, self-management reconciliation, and boundary checks
that prove there are no real Vultr API calls, no public DNS calls, no remote
workloads, and no application-cluster reconciliation. Network access may be
used by the preinstall/cache step to obtain tools and controller images; the
GitOps verification path itself runs against kind and a local Git source.

Ticket-ready framing, mirroring INIT-001: **Subsystem** is Deployment
Substrate / GitOps Substrate; **Phase** is Phase 5 foundation, second
dependency after INIT-008; **Executive priority** is the reconciliation gate
for the control cluster. The Phase 5 index names INIT-009 as Flux CD +
Kustomize + SOPS+age, and the two-tier memory file says INIT-008 creates the
control cluster while INIT-017 creates application clusters. Phase 1 research
found a 38-file `k8s/` tree and no active SOPS+age substrate; Q2 and Q4 close
those gaps by requiring deletion of `k8s/` and per-channel recipients.

---

## 2. Architecture

### 2.1 Control-cluster boundary

INIT-009 owns Flux on the control cluster only.

The control cluster is the cluster described by INIT-008's active
`infra/channels/dev.yaml` channel:

- `id: dev`
- `exposure: dev`
- `enabled_platforms: [kubernetes]`
- `cluster.label: humility-dev-platform`
- `state.key: channels/dev/terraform.tfstate`

Within INIT-009, `dev` is not an application environment. It is the Phase 5
control-cluster channel. This binds D1, D2, D7, and D12.

Flux on this control cluster reconciles Flux itself plus later manifests from
INIT-017, INIT-018, and INIT-019. It does not reconcile `services/api`,
`services/discord`, CloudNativePG, app-cluster ingress, app-cluster auth, or
app-cluster observability.

Those surfaces depend on INIT-017 because no application cluster exists before
Crossplane claims and compositions create one.

### 2.2 Repo layout

The implementation leaves the repo with this shape:

```text
gitops/
  bases/
    flux-system/
      README.md
      kustomization.yaml
      gotk-components.yaml
      gotk-sync.yaml
      source-gitrepository.yaml
      root-kustomization.yaml
    crossplane/
      README.md
      kustomization.yaml
    cert-manager/
      README.md
      kustomization.yaml
    external-dns/
      README.md
      kustomization.yaml
    cluster-security/
      README.md
      kustomization.yaml
  channels/
    dev/
      README.md
      kustomization.yaml
      flux-system.yaml
      patches/
        flux-source-local.yaml
  secrets/
    dev/
      .sops.yaml
      README.md
      bootstrap-creds.enc.yaml
  scripts/
    install-tools.sh
    bootstrap-flux.sh
  tests/
    validate_gitops.sh
  README.md
```

The old layout is deleted:

```text
k8s/
```

No alias, symlink, `legacy/` directory, wrapper script, or migration adapter
keeps `k8s/` live. This binds Q2 and D5.

### 2.3 Bases

`gitops/bases/` contains shared Kustomize bases.

`gitops/bases/flux-system/` is an active base. It contains the Flux controller
install manifest, Flux source object, and Flux Kustomization that points back
at the `dev` channel root.

`gitops/bases/crossplane/` is an empty handoff base for INIT-017.

`gitops/bases/cert-manager/` is an empty handoff base for INIT-018.

`gitops/bases/external-dns/` is an empty handoff base for INIT-018.

`gitops/bases/cluster-security/` is an empty handoff base for INIT-019.

The downstream bases are not deferred stubs. Each directory is tracked by a
README and an empty Kustomize file that names the owning initiative, explains
why no resources are expected today, and makes early resource additions a
scope violation.

### 2.4 Dev channel

`gitops/channels/dev/` is the only active channel overlay in INIT-009.

It composes:

- `../../bases/flux-system`
- `../../bases/crossplane`
- `../../bases/cert-manager`
- `../../bases/external-dns`
- `../../bases/cluster-security`
- `../../secrets/dev`

The overlay may include patches that are specific to the local control-cluster
verification path. The required patch is the local Git source URL used by the
kind harness. That patch still points at this same repository, but it points
at a local/in-cluster Git endpoint seeded from the current worktree so the
verification does not depend on a public network.

The overlay does not include an application-cluster root. This binds D1 and
D2 to the two-tier clarification.

### 2.5 Flux source repository

Flux uses this `server-manager` repository as the source of truth. This binds
Q3 and D6.

The Flux source object is a `source.toolkit.fluxcd.io/v1` `GitRepository`
named `server-manager` in `flux-system`.

Required properties:

- `interval: 1m`
- `ref.branch`: the branch under test or the branch configured by the
  bootstrap script.
- `url`: same repo, supplied for local verification by the kind harness.
- `ignore`: excludes non-GitOps paths only if the implementation proves Flux
  source artifacts still include `gitops/`.

For local verification, `bootstrap-flux.sh` creates a local read-only Git
source from the current worktree, such as an in-cluster Git service seeded
from `git bundle`, a local container reachable from kind, or another
Flux-compatible local HTTP Git endpoint. The implementation must not require
GitHub, a hosted Git service, or Vultr to prove INIT-009 locally.

For future real deployment, the same `GitRepository` kind remains valid; the
URL value changes when a real control cluster bootstrap initiative supplies a
reachable repo URL. INIT-009 does not implement that real deployment path.

### 2.6 Flux self-management

Flux installation manifests live under:

```text
gitops/bases/flux-system/
```

`gotk-components.yaml` contains the Flux controllers needed for the control
cluster. `gotk-sync.yaml`, `source-gitrepository.yaml`, or equivalent split
files define the Git source and root Kustomization.

Once bootstrapped, Flux reconciles its own install drift from Git. The local
bootstrap sequence is:

1. Create or reuse the kind cluster.
2. Run `flux check --pre` against the new cluster and require exit 0.
3. Make the current repo available to the cluster as a local Git source.
4. Run `flux bootstrap`, or apply the Flux source manifests with
   `kustomize build | kubectl apply`.
5. Apply the Flux source and root Kustomization if they were not already
   applied by bootstrap.
6. Wait for source reconciliation.
7. Wait for root Kustomization reconciliation.
8. Run post-install `flux check` and require exit 0.
9. Run a smoke reconcile of the empty downstream bases.

The bootstrap script may use `kubectl apply` for the initial controller seed.
After that, Flux owns the steady-state install. This closes D9 and D10.

### 2.7 Flux Kustomization topology

INIT-009 chooses a hybrid source-root plus channel-root topology:

- one `GitRepository` source named `server-manager`;
- one active root `Kustomization` named `dev-control` or
  `dev-control-root`;
- future component Kustomizations may be added by INIT-017, INIT-018, or
  INIT-019 only when they need independent ordering or health checks.

This is not one Kustomization per future app cluster. It is one active
control-cluster channel root for INIT-009. This closes D1 and D2.

Required root Kustomization properties:

- `interval: 5m`
- `retryInterval: 1m`
- `timeout: 5m`
- `path: ./gitops/channels/dev`
- `prune: true`
- `wait: true`
- `sourceRef.kind: GitRepository`
- `sourceRef.name: server-manager`

The `GitRepository` source uses `interval: 1m`.

This accepts the D9 default of report-plus-reconcile drift: Flux reports drift
through status and events, then reconciles it because `prune: true` and Flux's
apply loop are active.

### 2.8 Kustomize layout

INIT-009 chooses raw YAML plus Kustomize. This closes D7 and D8.

The channel-to-Kustomize mapping is:

- shared component manifests live in `gitops/bases/<component>/`;
- active channel composition lives in `gitops/channels/<channel-id>/`;
- per-channel patches live below the channel overlay;
- per-channel encrypted secrets live in `gitops/secrets/<channel-id>/`;
- future channel inheritance maps to Kustomize overlays and patches, not to
  hard environment roots.

There is no Helm chart hosting in INIT-009.

If later initiatives consume upstream Helm charts for Crossplane,
cert-manager, or ExternalDNS, those initiatives either vendor rendered YAML
into their bases or propose a new Kustomize-compatible ingestion strategy
inside their own pipeline. INIT-009 does not add Flux `HelmRepository` or
`HelmRelease` objects.

### 2.9 SOPS+age workflow

SOPS and age are mandatory in INIT-009. This closes Q4 and D4.

Each channel has its own `.sops.yaml`:

```text
gitops/secrets/dev/.sops.yaml
```

The file contains a creation rule scoped to the channel's encrypted secrets,
for example:

```yaml
creation_rules:
  - path_regex: gitops/secrets/dev/.*\.enc\.yaml$
    encrypted_regex: ^(data|stringData)$
    age: age1...
```

Age keys are operator-supplied or generated locally by the bootstrap workflow.
Private keys are never committed. Public recipients are committed in the
channel `.sops.yaml`.

#### Channel add/remove lifecycle for age recipients

This is a runbook contract, not an automation requirement. Tooling such as
`gitops/scripts/rotate-channel-key.sh` is anti-scope for INIT-009.

Adding a channel:

1. Operator runs `age-keygen` to produce a new age key for that channel.
2. Operator stores the private key locally at
   `~/.config/sops/age/<channel>.txt`, either gitignored or outside the repo.
3. Operator adds the public key recipient to
   `gitops/secrets/<channel>/.sops.yaml`.
4. Subsequent encryption for that channel uses the new recipient
   automatically through the channel `.sops.yaml`.

Removing a channel:

1. Operator deletes `gitops/secrets/<channel>/`, including encrypted secrets
   and `.sops.yaml`.
2. Operator may delete `~/.config/sops/age/<channel>.txt`; local retention is
   operator discretion.
3. The `gitops/channels/<channel>/` overlay is removed by the SLICE-031
   disposal pattern plus INIT-017 channel onboarding/removal work.
4. Flux prunes the orphaned channel reconciliation because channel roots use
   `prune: true`.

Rotating a recipient:

1. Add the new recipient public key to `.sops.yaml`.
2. Re-encrypt all channel secrets:
   `find gitops/secrets/<channel> -name '*.enc.yaml' | xargs -I{} sops updatekeys {}`.
3. Remove the old recipient from `.sops.yaml`.
4. Re-encrypt with the same `sops updatekeys` invocation to drop the old
   recipient.

The bootstrap workflow must generate a local age key when none is configured,
write the private key outside the repo, export `SOPS_AGE_KEY_FILE` for
verification, and decrypt the sample fixture during validation. Rotation
tooling is explicitly deferred beyond Phase 5.

### 2.10 Local verification architecture

Local verification uses kind. This closes Q1 and D3.

The verification stack consists of installed tools, a kind cluster, a local
Git source seeded from this worktree, Flux controllers, Flux source/root
reconciliation, SOPS decrypt, Kustomize render checks, and boundary checks.
The harness must not call Vultr or Cloudflare, run `tofu apply`, push images,
deploy workloads, create app clusters, or depend on public Git hosting.

Tool acquisition is owned by the preinstall slice. Once tools and any required
controller images are cached, validation runs against local kind and local Git.

Required tool minimums:

| Tool | Minimum | Evidence / source |
| --- | --- | --- |
| `flux` CLI | `>= 2.8.0` | current stable minor from Flux v2.8.x releases. |
| `kind` | `>= 0.31.0` | current stable release line. |
| `sops` | `>= 3.10.0` | current stable minor from SOPS v3.10.x releases. |
| `age` | `>= 1.3.0` | current stable minor from age v1.3.x releases. |
| `age-keygen` | `>= 1.3.0` | bundled with the same age release as `age`. |
| `kubectl` | `>= 1.31.0` | local Phase 1 verification has `v1.34.1`. |
| embedded Kustomize | `v5.7.1` | local `kubectl v1.34.1` reports embedded Kustomize `v5.7.1`. |

`gitops/scripts/install-tools.sh --check` must print the installed version for
each required tool and exit non-zero when any tool is absent or below its
minimum. Kustomize validation uses `kubectl version --client=true
--output=yaml` and the embedded `kustomizeVersion`; a standalone `kustomize`
binary is not required by INIT-009.

### 2.11 Decision closure matrix

| Decision | Binding in this proposal |
| --- | --- |
| D1 - Channel-to-Flux mapping | `gitops/channels/dev` is the active control-cluster channel root. |
| D2 - Flux Kustomization cardinality | one source plus one active control-cluster root Kustomization; component Kustomizations only when later initiatives need ordering. |
| D3 - Local cluster choice | kind. |
| D4 - SOPS+age custody | per-channel age recipients; private keys operator-local. |
| D5 - Existing `k8s/` disposal | delete entire tree. |
| D6 - Flux source repository | same `server-manager` repo. |
| D7 - Kustomize inheritance | bases plus channel overlays. |
| D8 - Manifest packaging | raw YAML plus Kustomize; no Helm surface in INIT-009. |
| D9 - Cadence and drift | GitRepository `1m`; Kustomization `5m`; `prune: true`; `wait: true`. |
| D10 - Local verification | full kind harness with Flux install/reconcile, Kustomize build, and SOPS decrypt. |
| D11 - Toolchain install | executable preinstall script owns required tools. |
| D12 - INIT-008 dependency | implementation consumes or mirrors INIT-008 `dev` channel input before hookpoints/implementation. |

---

## 3. Slice decomposition

### SLICE-031 - Toolchain preinstall and legacy `k8s/` disposal

**Scope:** SLICE-031 creates the executable toolchain entrypoint and removes
the stale GitOps authority. It implements `gitops/scripts/install-tools.sh`
as an idempotent Linux-first installer/checker for `flux`, `kind`, `sops`,
`age`, `age-keygen`, `kubectl`, and Kustomize execution. It deletes the full
38-file `k8s/` tree and removes or rewrites tests that assert the old
environment triad. This slice closes D3, D5, D10, and D11 at the substrate
entrypoint.

**Files this slice touches:**

- `gitops/scripts/install-tools.sh`
- `gitops/tests/validate_gitops.sh`
- `k8s/` deleted entirely
- stale test references to `k8s/`
- any shellcheck or executable-bit metadata needed for the new scripts

**Local-verification acceptance criteria:**

```bash
bash gitops/scripts/install-tools.sh --check
bash gitops/scripts/install-tools.sh
bash gitops/scripts/install-tools.sh --check
test ! -e k8s
rg 'k8s/(base|clusters|overlays)' . --glob '!plans/**' --glob '!.pipeline/**' && exit 1 || true
```

`--check` must produce non-mutating version output and fail clearly when a
required tool is absent or below its pinned minimum. It must report `flux`
`>= 2.8.0`, `kind` `>= 0.31.0`, `sops` `>= 3.10.0`, `age` and `age-keygen`
`>= 1.3.0`, `kubectl` `>= 1.31.0`, and embedded Kustomize `v5.7.1` from
`kubectl`. The installer must be idempotent on a configured machine.

**Dependencies:** none.

**Magnitude:** M.

**Anti-scope:** no Flux manifests, no SOPS policy, no kind cluster creation,
no macOS/Windows installer parity, no compatibility wrapper for `k8s/`.

### SLICE-032 - `gitops/` directory and Kustomize base/overlay layout

**Scope:** SLICE-032 creates the root-level `gitops/` tree and channel-aligned
Kustomize structure. It adds active structure for Flux and documented empty
handoff bases for Crossplane, cert-manager, ExternalDNS, and cluster security.
The empty bases are authorized handoff seams for INIT-017, INIT-018, and
INIT-019, not TODO stubs. This slice closes D1, D2, D7, D8, and D12 at the
path-contract level.

**Files this slice touches:**

- `gitops/README.md`
- `gitops/bases/flux-system/README.md`
- `gitops/bases/flux-system/kustomization.yaml`
- `gitops/bases/crossplane/README.md`
- `gitops/bases/crossplane/kustomization.yaml`
- `gitops/bases/cert-manager/README.md`
- `gitops/bases/cert-manager/kustomization.yaml`
- `gitops/bases/external-dns/README.md`
- `gitops/bases/external-dns/kustomization.yaml`
- `gitops/bases/cluster-security/README.md`
- `gitops/bases/cluster-security/kustomization.yaml`
- `gitops/channels/dev/README.md`
- `gitops/channels/dev/kustomization.yaml`
- `gitops/secrets/dev/README.md`
- `gitops/tests/validate_gitops.sh`

**Local-verification acceptance criteria:**

```bash
kubectl kustomize gitops/channels/dev >/tmp/init-009-dev.yaml
test -s /tmp/init-009-dev.yaml
bash gitops/tests/validate_gitops.sh --layout-only
```

The layout validation must assert that only `gitops/channels/dev` is active,
that downstream bases name their owning initiatives, and that no
`dev/staging/production` environment roots are recreated.

**Dependencies:** SLICE-031 for test harness entrypoint and `k8s/` deletion.

**Magnitude:** M.

**Anti-scope:** no controller payloads for Crossplane, cert-manager,
ExternalDNS, or security policies; no application workload directories; no
additional active channels.

### SLICE-033 - Flux self-management manifests and dev channel root

**Scope:** SLICE-033 adds the active Flux manifest base and the `dev`
control-cluster root. It vendors or generates the Flux controller manifest in
`gitops/bases/flux-system/`, defines the `server-manager` GitRepository, and
defines the root Kustomization that reconciles `./gitops/channels/dev`. The
source cadence is `1m`; the root Kustomization cadence is `5m`; prune and
wait are enabled. This slice closes D1, D2, D6, D8, D9, and D10 for Flux
itself.

**Files this slice touches:**

- `gitops/bases/flux-system/gotk-components.yaml`
- `gitops/bases/flux-system/gotk-sync.yaml`
- `gitops/bases/flux-system/source-gitrepository.yaml`
- `gitops/bases/flux-system/root-kustomization.yaml`
- `gitops/bases/flux-system/kustomization.yaml`
- `gitops/channels/dev/flux-system.yaml`
- `gitops/channels/dev/patches/flux-source-local.yaml`
- `gitops/tests/validate_gitops.sh`

**Local-verification acceptance criteria:**

```bash
kubectl kustomize gitops/channels/dev >/tmp/init-009-dev.yaml
grep -q 'kind: GitRepository' /tmp/init-009-dev.yaml
grep -q 'kind: Kustomization' /tmp/init-009-dev.yaml
grep -q 'interval: 1m' /tmp/init-009-dev.yaml
grep -q 'interval: 5m' /tmp/init-009-dev.yaml
grep -q 'prune: true' /tmp/init-009-dev.yaml
grep -q 'wait: true' /tmp/init-009-dev.yaml
bash gitops/tests/validate_gitops.sh --flux-render-only
```

The validation must also assert that no Flux Kustomization path points at
application workloads or app-cluster roots.

**Dependencies:** SLICE-031 and SLICE-032.

**Magnitude:** M.

**Anti-scope:** no app-cluster Flux, no Crossplane installation, no Helm
repositories, no real remote repo credentials, no production bootstrap URL.

### SLICE-034 - SOPS+age per-channel secrets workflow

**Scope:** SLICE-034 adds the SOPS+age policy and encrypted sample secret for
the `dev` channel. It records per-channel public recipients in
`gitops/secrets/dev/.sops.yaml`, ensures private keys remain operator-local,
and extends validation to decrypt the sample secret with a generated or
configured age key. This slice closes D4 and D10 for secret-management proof.

**Files this slice touches:**

- `gitops/secrets/dev/.sops.yaml`
- `gitops/secrets/dev/bootstrap-creds.enc.yaml`
- `gitops/secrets/dev/README.md`
- `gitops/scripts/bootstrap-flux.sh`
- `gitops/tests/validate_gitops.sh`
- `gitops/README.md`

**Local-verification acceptance criteria:**

```bash
age-keygen -o /tmp/init-009-dev-age.key
export SOPS_AGE_KEY_FILE=/tmp/init-009-dev-age.key
sops --decrypt gitops/secrets/dev/bootstrap-creds.enc.yaml >/tmp/init-009-secret.yaml
grep -q 'apiVersion:' /tmp/init-009-secret.yaml
bash gitops/tests/validate_gitops.sh --sops-only
```

If the sample encrypted secret is generated from a deterministic fixture, the
private key must still be local-only and must not be committed.

`gitops/README.md` and `gitops/secrets/dev/README.md` must document the manual
add, remove, and rotate lifecycle for channel age recipients. They must state
that rotation tooling is not part of INIT-009 and that local private-key
retention is an operator decision.

**Dependencies:** SLICE-031 and SLICE-032.

**Magnitude:** M.

**Anti-scope:** no key rotation tooling, no multi-operator workflow, no real
Discord tokens, no real Vultr or Cloudflare credentials, no sealed-secrets
controller.

### SLICE-035 - Local kind verification harness

**Scope:** SLICE-035 creates `gitops/scripts/bootstrap-flux.sh` and completes
`gitops/tests/validate_gitops.sh`. The bootstrap script creates or reuses a
kind cluster, runs `flux check --pre` against that cluster, exposes the
current repo to the cluster through a local Git source, installs Flux
controllers, applies the dev control-cluster root, waits for reconciliation,
runs `flux check`, and verifies the empty downstream bases reconcile without
deploying future controllers. This slice closes D3, D6, D9, D10, and D11 in
the end-to-end local proof.

**Files this slice touches:**

- `gitops/scripts/bootstrap-flux.sh`
- `gitops/tests/validate_gitops.sh`
- `gitops/channels/dev/patches/flux-source-local.yaml`
- `gitops/bases/flux-system/*`
- `gitops/README.md`

**Local-verification acceptance criteria:**

```bash
bash gitops/scripts/install-tools.sh --check
bash gitops/scripts/bootstrap-flux.sh --cluster humility-gitops-dev
flux check
flux get sources git -A
flux get kustomizations -A
bash gitops/tests/validate_gitops.sh --cluster humility-gitops-dev
```

The bootstrap sequence is: bring up kind, run `flux check --pre` and require
exit 0, run `flux bootstrap` or `kustomize build | kubectl apply` for the Flux
source manifests, then run post-install `flux check` and require exit 0.
`gitops/tests/validate_gitops.sh` must include
`assert_flux_check_pre_passes`.

The harness must fail if it detects real Vultr calls, real Cloudflare calls,
`tofu apply`, app workload manifests, or application-cluster Flux roots.

**Dependencies:** SLICE-031, SLICE-032, SLICE-033, and SLICE-034.

**Magnitude:** L.

**Anti-scope:** no real VKE cluster bootstrap, no external Git hosting
dependency for verification, no application-cluster provisioning, no image
push, no workload deployment.

### SLICE-036 - Documentation and handoff to INIT-017/018/019

**Scope:** SLICE-036 documents the GitOps layout, channel-overlay convention,
SOPS+age custody model, local verification commands, and downstream handoff
contract. It updates `infra/README.md` so INIT-008's control-cluster channel
points readers to the GitOps layer instead of the old environment roots. It
also revises or disposes stale GitOps planning material so this proposal is
the active authority. This slice closes D12 and makes the later initiatives'
entrypoints unambiguous.

**Files this slice touches:**

- `gitops/README.md`
- `infra/README.md`
- `plans/proposals/gitops-foundation.md`
- `plans/research/gitops-foundation.md`
- `plans/research/gitops-foundation-needs.md`
- `plans/research/gitops-foundation-hookpoints.md`
- any local index or planning note that still names `k8s/` as active

**Local-verification acceptance criteria:**

```bash
bash gitops/tests/validate_gitops.sh --docs-only
rg 'infra/environments/(dev|staging|production)' infra gitops plans/proposals/gitops-foundation.md && exit 1 || true
rg 'k8s/(base|clusters|overlays)' infra gitops plans/proposals/gitops-foundation.md && exit 1 || true
```

The docs must name INIT-017, INIT-018, and INIT-019 as owners of their empty
bases and must state that application-cluster Flux is INIT-017's
responsibility.

**Dependencies:** SLICE-031 through SLICE-035.

**Magnitude:** S.

**Anti-scope:** no new research, no implementation of downstream manifests,
no deployment runbook for real Vultr clusters, no production channel.

### Slice dependency order

```text
SLICE-031
  -> SLICE-032
    -> SLICE-033
    -> SLICE-034
      -> SLICE-035
        -> SLICE-036
```

SLICE-033 and SLICE-034 can proceed in parallel after SLICE-032 because Flux
rendering and SOPS policy touch different files. SLICE-035 integrates both.

---

## 4. Tradeoffs accepted

### Per-channel age recipients

INIT-009 uses per-channel age recipients. This matches Q4 and closes D4, but
it creates one public-recipient set per channel and requires operators to keep
private keys organized outside the repo. Rotation tooling is not in INIT-009.
The risk gate should validate that documenting operator-local custody is
acceptable for single-operator Phase 5.

### Single-repo GitOps source

Flux reads from the same `server-manager` repo. This closes Q3 and D6 and
keeps local verification simple, but it means application code, infra code,
and desired cluster state share one commit history. The mitigation is a hard
root-level `gitops/` boundary, validation that Flux paths stay under
`gitops/channels/dev`, and no external GitOps repo until a later deployment
initiative explicitly proposes one.

### Linux-first toolchain installer

INIT-009 ships an executable preinstall script. This closes Q5 and D11, but
the script is Linux-first and OS-coupled. macOS and Windows operator support
can be documented as non-primary paths. CI and agents rely on the script, not
on a README paragraph.

### Kustomize over Helm

INIT-009 chooses raw YAML plus Kustomize. This closes D8 and matches the
channel-overlay pattern, but it means upstream controllers introduced later
are represented as vendored/rendered manifests or as a new proposal in their
own initiatives. INIT-009 does not introduce Flux Helm APIs.

### Local-only bootstrap

The Flux bootstrap proof targets kind only. This closes D3 and D10 and honors
Phase 5, but it does not prove a real Vultr VKE bootstrap. Real cluster
bootstrap is a separate post-Phase-5 deployment initiative.

### Empty downstream bases

INIT-009 ships empty bases for INIT-017, INIT-018, and INIT-019. This creates
clear handoff paths but risks looking like deferred stubs. The mitigation is
that each base is documented as an authorized handoff seam with a named owning
initiative and no silent behavior.

### Local Git source in kind

The local harness uses a local/in-cluster Git source seeded from the current
repo. This proves Flux reconciliation without public Git or Vultr, but it
adds harness complexity. The risk gate should validate that this complexity is
worth the no-internet/local-only guarantee.

---

## 5. Hookpoints (preview)

### Existing `k8s/` tree

Action: delete in SLICE-031. The current tree has 38 tracked files under
`k8s/base/`, `k8s/clusters/{dev,staging,production}/`,
`k8s/overlays/{dev,staging,production}/`, and
`k8s/tests/test_gitops_foundation.sh`. It encodes hard environments and both
app/control cluster roots, which conflicts with Q2, D5, channel inheritance,
and the control-cluster-only scope.

### Existing GitOps proposal

Path: `plans/proposals/gitops-foundation.md`.

Action: revise or banner-mark in SLICE-036. Keep useful concepts about Flux
as reconciler and scoped paths; remove environment-shaped, app-cluster, or
non-control-cluster language.

### Existing GitOps research files

Paths:

- `plans/research/gitops-foundation.md`
- `plans/research/gitops-foundation-needs.md`
- `plans/research/gitops-foundation-hookpoints.md`

Action: supersede, revise, or delete in SLICE-036. Surviving findings should
be embedded in the new proposal/docs; old `k8s/` or environment-triad
language must stop acting as live authority.

### `infra/README.md`

Action: update in SLICE-036. It still describes
`infra/environments/{dev,staging,production}` and must cross-link the INIT-008
channel model plus the new `gitops/` root.

### New `gitops/` directory

Action: create in SLICE-032 and populate across SLICE-033 through SLICE-036.
This becomes the only active GitOps authority.

### Existing platform bootstrap harness

Path: `infra/tests/validate_platform_bootstrap.sh`.

Action: preserve and keep green. INIT-009 may add cross-links or independent
GitOps validation, but it must not break the INIT-008 local infra harness.

---

## 6. Acceptance criteria for INIT-009

1. `bash gitops/scripts/install-tools.sh` succeeds on a clean Linux dev
   machine and is idempotent on a configured machine.
2. `bash gitops/scripts/install-tools.sh --check` reports versions for
   `flux`, `kind`, `sops`, `age`, `age-keygen`, `kubectl`, and embedded
   Kustomize, and exits non-zero when any tool is below its pinned minimum.
3. `bash gitops/scripts/bootstrap-flux.sh --cluster humility-gitops-dev`
   brings up kind, runs `flux check --pre` before installing Flux, installs
   Flux, exposes this repo as local Git, reconciles `gitops/channels/dev`, and
   reports green.
4. The bootstrap transcript or harness assertion proves `flux check --pre`
   passed before installation; post-install `flux check`,
   `flux get sources git -A`, and `flux get kustomizations -A` report ready
   state after bootstrap.
5. `kubectl kustomize gitops/channels/dev` or `kustomize build
   gitops/channels/dev` produces complete YAML with Flux objects and no app
   workload deployments.
6. `sops --decrypt gitops/secrets/dev/bootstrap-creds.enc.yaml` works with
   the operator's age key.
7. `gitops/secrets/dev/.sops.yaml` contains only dev-channel creation rules
   and recipients.
8. `gitops/README.md` documents layout, channel overlays, self-managing Flux,
   SOPS+age custody, and local verification commands.
9. Placeholder base READMEs name their owners: Crossplane -> INIT-017;
   cert-manager and ExternalDNS -> INIT-018; cluster-security -> INIT-019.
10. The `k8s/` tree is gone, and active docs/tests under `infra/` and
    `gitops/` no longer point at `k8s/base`, `k8s/clusters`, or
    `k8s/overlays`.
11. `infra/tests/validate_platform_bootstrap.sh` continues to pass.
12. `gitops/tests/validate_gitops.sh` checks layout, rendering, SOPS decrypt,
    Flux source/root properties, and forbidden cloud/workload boundaries.
13. No real Vultr, DNS, ACME, app workload, application cluster, app-cluster
    Flux, HelmRelease, or HelmRepository surface is introduced.
14. Stale GitOps planning materials are revised, banner-marked, superseded, or
    deleted so this proposal is the active authority.

---

## 7. Anti-scope

- Application workloads from INIT-010 through INIT-014.
- Container image build, tag, push, registry auth, or smoke-run delivery.
- Buildkite pipeline authoring or Buildkite agent validation.
- Crossplane install manifests, providers, ProviderConfigs, XRDs,
  Compositions, or claims.
- cert-manager install manifests, ACME issuers, certificates, or challenge
  flows.
- ExternalDNS install manifests, Cloudflare tokens, zones, or record writes.
- Cluster security manifests, NetworkPolicies, Pod Security Standards, or
  RBAC baselines.
- Real Vultr cluster bootstrap.
- `tofu apply` against any root.
- Multi-cluster Flux federation.
- Application-cluster Flux bootstrap.
- Helm chart hosting or Flux Helm APIs.
- Secret rotation tooling.
- Multi-operator key management.
- Production, staging, internal, customer, or ephemeral active channels.
- Public DNS, public ingress, public-audience publish, or Discord-visible
  mutation.
- Any compatibility path for `k8s/`.

---

## 8. Stale material disposal

### `plans/proposals/gitops-foundation.md`

Action: revise and banner-mark in SLICE-036 unless hookpoints determine full
deletion is cleaner.

Keep only concepts still true after this proposal:

- Flux is the reconciler.
- Git is desired state.
- Buildkite must not mutate clusters.
- paths must be scoped and testable.

Remove or supersede:

- environment-triad roots;
- app-cluster Flux ownership by INIT-009;
- any language that says INIT-009 does not write Flux manifests;
- any hosting or promotion model that assumes real deployment in Phase 5.

### `plans/research/gitops-foundation.md`

Action: supersede or delete if the useful evidence is fully embedded in
`.pipeline/research.md`, `.pipeline/synthesis.md`, this proposal, and
`gitops/README.md`.

Reason: stale SealedSecrets, environment layout, and older root-shape
assumptions can mislead implementation.

### `plans/research/gitops-foundation-needs.md`

Action: revise only if it can be reduced to evergreen needs language;
otherwise supersede/delete.

Keep only:

- need for scoped paths;
- need for local verification;
- need for Flux entrypoints;
- need for CI/CD to observe rather than mutate.

Remove or supersede:

- hard environment references;
- non-channel inheritance language;
- any implication that application workload manifests belong in INIT-009.

### `plans/research/gitops-foundation-hookpoints.md`

Action: delete or supersede.

Reason: hookpoints must be rerun after the risk gate. The existing file
assumes a greenfield or old-shape `k8s/` root and is not a valid Phase 5
hookpoint map.

### Historical risk files

Paths:

- `plans/risk/gitops-foundation-audit.md`
- `plans/risk/gitops-foundation-scope.md`
- `plans/risk/gitops-foundation-shortcut.md`

Action: leave as historical unless implementation touches the risk directory.

Prior LOW findings do not approve this proposal. The control-cluster-only,
per-channel SOPS, same-repo, and local-Git-source choices need a new risk
gate.

---

## 9. Risk-gate observations

The proposal has no unresolved decisions that block risk review. It does have
observations the risk gate should validate.

Risk reviewers should validate five observations: local Git source complexity
must stay inside test/bootstrap code; the installer may need network access
only for tool/image acquisition; empty downstream bases must remain explicit
handoff seams; `dev` must remain the only active channel; and app-cluster Flux
must remain INIT-017's Crossplane responsibility.

---

## 10. Revision history

- Round 1 closes AUD-001 by adding pinned tool minimums in Section 2.10,
  requiring `install-tools.sh --check` to print versions and fail below the
  pins, and carrying those pins into SLICE-031 and INIT-009 acceptance
  criteria.
- Round 1 closes AUD-002 by requiring `flux check --pre` before Flux
  installation in the Section 2.6 bootstrap sequence and SLICE-035, with
  `assert_flux_check_pre_passes` as a harness acceptance criterion.
- Round 1 closes AUD-003 by documenting the manual per-channel age recipient
  add/remove/rotate lifecycle in Section 2.9 and making that runbook
  documentation an explicit SLICE-034 acceptance requirement.
