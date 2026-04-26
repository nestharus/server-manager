# INIT-102 Synthesis

This synthesis binds INIT-102's design decisions before the proposal phase.
Each D-record names a decision, the research evidence supporting it, the
alternatives rejected, and the consequence for the proposal phase and
downstream INITs. Synthesis is grounded in research only; no decision below
introduces design specifics beyond what is needed to bind the choice.

Source: `worktrees/init-102-gitops-substrate/.pipeline/research.md`. Section
references below use that file unless otherwise noted.

## Decision Records

### D1 — D-FLUX-INSTALL

**Decision**: INIT-102 generates the Flux controller install manifest with
`flux install --export`, vendors the result into the repo at
`gitops/flux/gotk-components.yaml`, and applies it through the channel
template's post-install path. INIT-102 does not run `flux bootstrap`.

**Evidence**: research §2.2. `flux install --export` separates controller
manifest generation from `GitRepository`/`Kustomization` wiring, giving an
explicit artifact boundary that matches the channel-template ownership of
repo layout. `flux bootstrap` combines initial install with Git wiring and
"must be constrained so it does not rewrite repo layout outside the channel
template," which conflicts with channel-template authority over `gitops/`
shape (research §2.2; channel-template memory cited at research §0).
`flux install` is a documented Flux subcommand and `--export` is documented
to emit YAML rather than apply it (research §2.2 citations).

**Alternatives rejected**:
- `flux bootstrap git`: combines install with `GitRepository`/root
  `Kustomization` creation and rewrites repo files; conflicts with
  channel-template-owned layout (research §2.2).
- Raw download of release-tagged `gotk-components.yaml`: lower
  reproducibility than the pinned-CLI export and offers no advantage over
  `flux install --export` (research §2.2 + §2.3 release tag evidence).

**Consequence**: SLICE-102.02 owns the vendored controller manifest. The
channel template applies it through the post-install path bound in D8 below,
not through a `flux bootstrap` invocation. Future remote channels apply the
same vendored artifact; no per-channel `flux bootstrap` is introduced.

---

### D2 — D-FLUX-COMPONENTS

**Decision**: INIT-102 ships only `source-controller` and
`kustomize-controller`. `helm-controller`, `notification-controller`,
`image-reflector-controller`, and `image-automation-controller` are excluded
from the INIT-102 vendored manifest.

**Evidence**: research §2.1. The minimum functional loop for raw manifests is
`source-controller` (fetches Git artifact) plus `kustomize-controller`
(applies a `Kustomization` path). `helm-controller` is needed only for
`HelmRelease` reconciliation, which INIT-102 excludes. `notification-controller`
ownership is assigned to INIT-117 (research §2.1; PHASE_5_INDEX:45). The
archived INIT-009 manifest included all six controllers (research §1.3),
which is wrong-shaped relative to INIT-102's scope.

**Alternatives rejected**:
- Full default Flux component set: pulls in Helm/notification/image surfaces
  that overlap INIT-103/INIT-117 ownership and inflate INIT-102's scope
  (research §2.1, §8.3).
- Source-controller only: kustomize-controller is required to apply manifests
  from the Git source, so source-controller alone cannot reconcile anything
  (research §2.1).

**Consequence**: The `flux install --export` invocation in D1 must use the
`--components=source-controller,kustomize-controller` selector. The vendored
manifest is smaller, and adding controllers later is an explicit edit rather
than implicit drift.

---

### D3 — D-GITOPS-LAYOUT

**Decision**: INIT-102 introduces a root-level `gitops/` tree with this
canonical shape:

```
gitops/
  flux/                       # vendored Flux controllers (D1)
  sources/<channel-id>/       # GitRepository CR + git-daemon (local channels)
  channels/<channel-id>/      # channel overlays (e.g., channels/local/)
  bootstrap/                  # SOPS-encrypted bootstrap-tier secrets + .sops.yaml
```

INIT-102 scope wires the `local` channel only. The `dev` channel overlay is
out of scope (deferred until a remote-channel slice). The stale top-level
`k8s/` tree is deleted in the same change.

**Evidence**: research §3. The channel-template memory says channel
inheritance maps to Kustomize bases/overlays and overlays should be keyed by
channel id, not hard environment names (research §0 + §3). INIT-101 active
channel ids are `local` and `dev` (research §3 + `infra/channels/local.yaml`,
`infra/channels/dev.yaml`). The current `k8s/` tree has 38 files, hard-env
overlays (`dev`/`staging`/`production`), placeholder Flux source URLs, and
includes `app-cluster` roots before INIT-106 (research §1.2). The
no-backwards-compatibility convention bans dual implementations and partial
migrations (research §0).

**Alternatives rejected**:
- Reshape `k8s/` in place into channel-named overlays: keeps a misleading
  name (channel content is more than k8s manifests; e.g., SOPS metadata),
  and `k8s/` already carries app-cluster paths that INIT-102 cannot keep
  (research §1.2).
- Keep `k8s/` parallel to `gitops/` during a transition: forbidden by
  no-backwards-compatibility convention (research §0).
- Wire `local` and `dev` channel overlays in INIT-102: `dev` is a remote
  Vultr-VM channel; INIT-102's done state is local k3d reconciliation only
  (research §0 + §1.1; PHASE_5_INDEX:96-130).

**Consequence**: SLICE-102.02 deletes `k8s/` and creates `gitops/`. Per-channel
Flux `Kustomization` `.spec.path` resolves to `./gitops/channels/<channel-id>`
(research §3 path evidence). Remote-channel overlays (e.g., `gitops/channels/dev/`)
are added by a later initiative.

---

### D4 — D-LOCAL-SOURCE

**Decision**: The local-channel Flux source is a Git server that runs
in-cluster (a local Git source Pod plus ClusterIP Service in a dedicated
`git-system` namespace) and is seeded from the working repo by the channel
bring-up script. The source URL is
`http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git`.

**Evidence**: research §5.2 Option B + §5.3 recommendation. Flux
`GitRepository` only needs a URL the source-controller can reach from inside
the cluster (research §5.1, §5.2). Archived INIT-009 already prototyped an
in-cluster Git service shape; INIT-102's final HTTP CGI URL is the binding
adaptation for Flux v2.8. Git-backed Flux is mandated by D8 (research §0).

**Alternatives rejected**:
- Option A — GitHub round-trip: every iteration requires commit/push before
  Flux can see changes, and the local-as-first-deployment frame explicitly
  forbids treating local as a hosted-Git client (research §5.2, §0).
- Option C — local OCI registry with `OCIRepository`: D8 names Git as the
  authoritative source model; OCI is at most a transport, not the
  authoritative source (research §5.2, §0).
- Option D — host-path mount into source-controller: no upstream Flux source
  API supports mounted host paths; couples to controller deployment shape
  (research §5.2).

**Consequence**: SLICE-102.05 owns the in-cluster Git server lifecycle
(Deployment, Service, seeding job/script). The proposal phase must still
choose: branch/ref name committed into channel YAML, auth posture (anonymous
read inside cluster vs. SSH), and re-seed cadence. `gitops.git_url` in the
local channel resolves to the in-cluster service URL.

---

### D5 — D-SOPS-BOUNDARY

**Decision**: SOPS+age in INIT-102 encrypts only **bootstrap-tier** files —
those needed to start runtime secret management — under
`gitops/bootstrap/*.enc.yaml`. Encryption is scoped to the
`data` and `stringData` fields via `encrypted_regex`. Examples of in-scope
files: a Flux Git deploy key for future remote channels and the bootstrap
credential used by INIT-103 to provision Infisical. **Out of scope for SOPS
encryption**: runtime application secrets (Discord tokens, database
credentials, API keys, per-tenant secrets) — those are owned by Infisical
under INIT-103.

**Evidence**: research §4.2 + §0. D8 binds SOPS+age as bootstrap-only and
Infisical as runtime secret store (DECISIONS.md:196-198). Phase 5 completion
criteria say SOPS+age bootstraps only secrets needed to start runtime secret
management (PHASE_5_INDEX:126-130). INIT-103 owns Infisical including the
Operator and `InfisicalSecret` CRDs (PHASE_5_INDEX:31). Enforcement is by
file content and ownership review, not by SOPS itself (research §4.2). SOPS
supports `encrypted_regex` to scope encryption to YAML fields (research §4.1).

**Alternatives rejected**:
- Encrypt all runtime secrets in SOPS: superseded by D8; previously recorded
  as a mistake in `environment-agnostic-stack.md:62-68` (research §0).
- Whole-file encryption: defeats `encrypted_regex` review surface and makes
  diff review harder for bootstrap content (research §4.1).

**Consequence**: SLICE-102.03 owns `.sops.yaml` creation rules limited to
`gitops/bootstrap/`, an `encrypted_regex` of `^(data|stringData)$`,
and a single bootstrap-tier sample/fixture demonstrating the pattern. Any
runtime secret introduced by a later INIT must go through Infisical, not SOPS.

---

### D6 — D-AGE-KEY-DELIVERY

**Decision**: The age private key is delivered to the cluster as the
Kubernetes Secret `sops-age` in namespace `flux-system`, key `age.agekey`,
created by an idempotent post-install step (`kubectl create secret generic
sops-age -n flux-system --from-file=age.agekey=$SOPS_AGE_KEY_FILE
--dry-run=client -o yaml | kubectl apply -f -`) invoked from the channel
bring-up flow. The age private key file lives at
`~/.config/sops/age/<channel-id>.txt` outside the repo. Public recipients are
committed in the repo-root `.sops.yaml` (bootstrap-tier custody is repo-wide,
not per-channel).

**Evidence**: research §4.3. Flux SOPS integration requires a Kubernetes
Secret in the same namespace as the `Kustomization`, referenced via
`.spec.decryption.secretRef`; Flux docs use exactly the
`kubectl create secret generic sops-age --namespace=flux-system
--from-file=age.agekey=...` shape (research §4.1, §4.3). The chicken-and-egg
constraint is explicit: Flux cannot decrypt encrypted bootstrap files until
the secret already exists in-cluster, so creation must happen out-of-band
before the encrypted-files reconciliation runs (research §4.3, §10). INIT-009
custody notes used `~/.config/sops/age/<channel>.txt` and committed public
recipients in channel `.sops.yaml` — salvageable shape (research §1.3, §4.3).

**Alternatives rejected**:
- Pure manual `kubectl create secret`: not idempotent, easy to drift between
  operators, fails the channel-template-as-source-of-truth shape (research
  §4.3, §6).
- Flux CLI helper (`flux create secret sops`): adds another CLI surface and
  does not align with the bring-up-script-driven channel pattern (research
  §6).
- Commit the age private key in any form: forbidden by SOPS bootstrap
  contract (research §4.2).

**Consequence**: SLICE-102.03 owns the `sops-age` secret delivery script and
the custody runbook. The channel YAML's resolved
`gitops.sops_age_secret_name` and `gitops.decryption_secret_namespace` (D7)
must match the values used by the script and the `Kustomization`'s
`.spec.decryption.secretRef`.

---

### D7 — D-CHANNEL-SCHEMA-EXT

**Decision**: Add a `gitops` block to both
`infra/schemas/platform-channel.schema.json` and the resolved schema, with
exactly these fields:

- `gitops.source_kind` — enum `git` (`oci` reserved for future, not accepted in INIT-102).
- `gitops.git_url` — Git URL the in-cluster `source-controller` can reach.
- `gitops.git_ref` — branch or tag (e.g., `main`).
- `gitops.path` — path within the source artifact (e.g., `./gitops/channels/local`).
- `gitops.interval` — `GitRepository.spec.interval` and root `Kustomization.spec.interval` (e.g., `1m`).
- `gitops.retry_interval` — root `Kustomization.spec.retryInterval` (e.g., `1m`).
- `gitops.kustomization_name` — root Flux source and kustomization name.
- `gitops.kustomization_namespace` — namespace containing the Flux source and kustomization.
- `gitops.sops_age_secret_name` — Kubernetes Secret name (default `sops-age`).
- `gitops.decryption_secret_namespace` — namespace (default `flux-system`).

`gitops.*` fields carry Flux source and bootstrap-decryption metadata only.
No runtime secret provider fields (those are INIT-103 / Infisical).

**Evidence**: research §6. Current schema has no `gitops` block (research §1.1
+ §6). Flux `GitRepository` requires `.spec.interval` and accepts `url`,
`ref`, `secretRef`; `Kustomization` requires `.spec.interval` and uses
`sourceRef`, `path`, decryption settings (research §2.3, §4.1). Possible
schema fields enumerated in research §6 are bound here verbatim with the
boundary concern explicitly applied: no Infisical/runtime-secret fields in
this block (research §6 boundary note + PHASE_5_INDEX:30-31).

**Alternatives rejected**:
- Put GitOps config outside `infra/channels/*.yaml` (e.g., a separate
  `gitops/channels/<id>/config.yaml`): breaks the channel-template
  single-source-of-truth shape (research §6 + channel-template memory at §0).
- Include `gitops.runtime_secret_provider` or similar Infisical fields:
  violates the INIT-102/INIT-103 boundary (research §6).
- Accept `oci` as a `source_kind` value now: D8 binds Git-backed Flux; OCI
  is reserved for a future initiative if needed (research §0, §5.2).

**Consequence**: SLICE-102.04 owns the schema additions, validator updates,
fixtures, and resolved-channel emission. Per-channel `gitops.*` values feed
the `GitRepository` and `Kustomization` manifests rendered in
`gitops/channels/<channel-id>/`.

---

### D8 — D-CHANNEL-TEMPLATE-INT

**Decision**: Flux installation and SOPS-age secret delivery are wired into
the channel via a **post-install bash script** invoked after cluster
bring-up (extending or chained from `infra/scripts/bring-up-local-channel.sh`),
not as a new OpenTofu module. The script reads the resolved channel YAML and
performs, in order: (1) `kubectl apply -f gitops/flux/gotk-components.yaml`,
(2) idempotent `sops-age` Secret apply (D6), (3) `kubectl apply` of the
channel's `GitRepository` + root `Kustomization` (rendered from `gitops.*`
fields per D7).

**Evidence**: research §6. INIT-101 uses scripts for local k3d lifecycle and
modules for cluster resources (research §6 + `infra/README.md:84-109`).
OpenTofu cannot safely hide cluster mutations without explicit contracts; in
this repo the script-vs-module split has already been resolved by INIT-101
toward scripts for cluster mutation (research §6). The kubeconfig is a
cluster-bring-up output, and Flux install depends on it — natural fit for a
post-bring-up script step (research §1.1, §6).

**Alternatives rejected**:
- New OpenTofu `platform-flux/` module using the `kubernetes`/`kubectl`
  providers: introduces CRD-ordering complexity and cross-provider
  dependencies inside the channel-template `main.tf` dispatch; not
  warranted by research evidence (research §6).
- Vanilla `flux bootstrap` invocation: rejected in D1 (rewrites repo
  layout).
- Inline Flux install inside the cluster module: collapses the
  cluster-substrate boundary set by INIT-101 (research §1.1 INIT-101
  anti-scope).

**Consequence**: SLICE-102.04/05 own the post-install script. The script
must be idempotent (re-runnable on an already-Flux-bearing cluster) and
deterministic (channel YAML is the only input besides the kubeconfig).

---

### D9 — D-INIT-009-DISPOSAL

**Decision**: Discard all INIT-009 wrong-shaped artifacts entirely. Nothing
from `worktrees/init-009-gitops-substrate/` is copied into INIT-102. Only
**structural ideas** are reused, re-derived from scratch against the current
constraints:

- Salvaged ideas: root-level `gitops/` layout (`flux/`, `sources/`,
  `channels/`, `bootstrap/`); `.sops.yaml` repo-root custody pattern with
  public recipient committed and private key outside repo; SOPS rotation
  runbook outline (`updatekeys` flow); the "in-cluster Git server" concept
  (D4).
- Discarded artifacts: kind-based local cluster (superseded by k3d/k3s);
  `dev` as active channel for local proof (superseded by `local`); the
  full six-controller `gotk-components.yaml`; placeholder `bootstrap-creds.enc.yaml`
  with empty `stringData`; `dev`-channel SOPS metadata; any
  SOPS-as-runtime framing.

Stale `k8s/` tree at the top of the current worktree is deleted in full —
no salvage (hard-env overlays, placeholder URLs, premature `app-cluster`
paths).

**Evidence**: research §1.3 (INIT-009 salvageable shape and wrong-shaped
detail); research §1.2 (current `k8s/` defects); research §0
(no-backwards-compatibility convention bans dual implementations and partial
migrations).

**Alternatives rejected**:
- Copy INIT-009's `gitops/` directory verbatim and patch: violates
  no-backwards-compatibility (kind-based, dev-channel, placeholder content
  is wrong-shaped; partial migration would fossilize the wrong shape).
- Keep `k8s/` and reshape: rejected in D3.
- Salvage INIT-009's `gotk-components.yaml`: pinned to v2.8.0 with all six
  controllers; D2 cuts the controller set and D9-tooling pin in this doc
  upgrades the version.

**Consequence**: SLICE-102.02 writes fresh `gitops/` against `local`
channel + k3d + selected controllers. The reference copy of INIT-009 stays
on its archived branch (research §1.3) and is not imported.

---

### D10 — D-TOOLCHAIN-VERSIONS

**Decision**: Pin (latest stable as of 2026-04-22):

- `flux` CLI: `v2.8.6` (released 2026-04-21).
- `sops`: `v3.12.2` (released 2026-03-18).
- `age` + `age-keygen`: `v1.3.1` (released 2025-12-28).

Standalone `kustomize` is **not** pinned (kubectl's embedded Kustomize
`v5.7.1` and Flux's bundled kustomize-controller cover INIT-102 needs).

The toolchain installer extends INIT-101's `infra/scripts/install-cluster-tools.sh`
(or a peer file) to install/verify the three new tools alongside the existing
k3d/OpenTofu/kubectl/Docker checks.

**Evidence**: research §7.1 (none of `flux`, `sops`, `age`, `age-keygen` are
installed locally on 2026-04-26). Research §7.2 latest-release evidence
(GitHub release pages cited). INIT-101 toolchain pins remain authoritative
for shared tools (research §7.2).

**Alternatives rejected**:
- Pin standalone Kustomize `v5.8.1`: not needed for INIT-102 (research §7.2,
  §10).
- Use distro packages without pinning: drifts across operators; INIT-101
  established the pinned-installer pattern (research §7.1, §7.2).
- Pre-release/RC versions: risk of API churn during Phase 5.

**Consequence**: SLICE-102.01 owns toolchain installer changes. The pinned
`flux` version flows into `gitops.flux_version` (D7) and the vendored
`gotk-components.yaml` (D1) so generation and runtime versions match.

---

### D11 — D-LOCAL-VERIFICATION

**Decision**: "Real reconciliation in local k3d" means the harness asserts
**all** of the following against a live k3d cluster, in order:

1. All Flux controller Deployments in `flux-system` (i.e.,
   `source-controller`, `kustomize-controller`) report
   `.status.availableReplicas == .spec.replicas`.
2. The root `GitRepository` reports `status.conditions[type=Ready].status="True"`
   with `.status.observedGeneration == .metadata.generation`.
3. The root `Kustomization` reports `status.conditions[type=Ready].status="True"`
   with current `observedGeneration`.
4. A sentinel target manifest reconciled by Flux exists in the cluster: a
   dedicated `Namespace` (e.g., `humility-gitops-sentinel`) and a
   `ConfigMap` inside it whose `data.channel == "local"` (or another
   deterministic key seeded from the channel YAML).
5. SOPS path: at least one bootstrap-tier `*.enc.yaml` reconciles
   successfully — verified by checking that a sentinel Secret derived from
   the encrypted bootstrap file exists in the expected namespace and decrypts
   to a known-good value.

**Evidence**: research §9 SLICE-102.05/06 (assertions for Flux health,
source readiness, Kustomization readiness, reconciled test manifest).
Research §0 + §5.1 forbid dry-run substitutes — every assertion is a real
cluster query, not a render check. Flux `Kustomization`/`GitRepository`
status conditions are documented (research §2.3).

**Alternatives rejected**:
- Render-only verification (`flux build`/`kustomize build` with no apply):
  forbidden by environment-agnostic memory + D8 (research §0).
- Skip the SOPS-path assertion: leaves D5/D6 unverified at completion.
- Verify only controller health: doesn't prove the source/`Kustomization`
  reconciled anything.

**Consequence**: SLICE-102.06 owns the harness. The sentinel manifest lives
under `gitops/bases/` (or a `gitops/channels/local/` overlay file) so it
reconciles through the channel root `Kustomization`. The harness fails fast
if any of the five assertions misses, mirroring INIT-101's
`kubectl get nodes`-as-proof pattern (research §1.1).

---

## Anti-scope (binding)

INIT-102 explicitly does **not** do any of the following. Each item is
deferred to the named successor or out of scope entirely.

- **Crossplane**, control-cluster Crossplane provider/configuration, and
  any application-cluster provisioning (INIT-106, INIT-017; research §0
  two-tier memory).
- **Infisical**, Infisical Operator, `InfisicalSecret` CRDs, and any
  runtime application secret store (INIT-103; research §4.2,
  PHASE_5_INDEX:31).
- **cert-manager**, **DNS** automation, **TLS** issuance, and ingress
  certificate plumbing (later Phase 5 INITs; research §1.1 INIT-101
  anti-scope).
- **Application workloads** (Discord daemon, API service, data plane,
  app-tier observability) and **application clusters** (later INITs;
  research §1.1 + §1.2 stale `k8s/app-cluster` evidence).
- **Observability**, alerting, and **notification-controller** features
  (INIT-117; research §2.1 + PHASE_5_INDEX:45).
- **Multi-tenancy** boundaries and Flux RBAC tenant carve-outs (INIT-115/116;
  research §8.3).
- **Helm** sources, `HelmRelease` reconciliation, and `helm-controller`
  (research §2.1, §8.3).
- **Image-reflector** and **image-automation** controllers (research §2.1).
- **Remote channel Flux installation** — the `dev` Vultr-VM channel's
  GitOps wiring is out of scope; INIT-102's done state is local k3d only
  (research §0 + §1.1, PHASE_5_INDEX:96-130).
- **Runtime secrets in SOPS** of any kind, regardless of how convenient —
  the SOPS boundary is content-and-ownership, and runtime secrets belong
  to Infisical (research §4.2, §8.3).
- **MinIO bucket-watched Flux** sources — superseded by Git-backed Flux
  per D8 (research §0; DECISIONS.md:229-230).

## Open questions (to resolve in proposal phase)

- **In-cluster Git server lifecycle (D4)**: concrete `Deployment` +
  `Service` shape for the `git daemon`, the seeding mechanism (init
  container that `git clone`s from a host volume vs. a one-shot `Job` vs.
  a sidecar that pulls from a host bind mount), branch/ref naming, and
  whether re-seeding is on-demand or interval-driven.
- **`gitops/` materialization order (D3)**: whether `k8s/` deletion and
  `gitops/` creation land in the same SLICE-102.02 commit (preferred per
  no-backwards-compatibility) or are split for review ergonomics.
- **`dev` channel placeholder (D3, D7)**: whether the resolved-schema-level
  `gitops` block is required for `dev.yaml` even though no `gitops/channels/dev/`
  overlay ships in INIT-102, or whether `dev.gitops` is left absent until a
  later remote-channel slice.
- **Sentinel manifest design (D11)**: exact `Namespace` name, `ConfigMap`
  name/key, and whether a SOPS-encrypted sentinel Secret is independent of
  or layered onto the bootstrap-tier sample required by D5.
- **Toolchain installer split (D10)**: extend
  `infra/scripts/install-cluster-tools.sh` in place vs. add a peer
  `install-gitops-tools.sh` that the bring-up script chains.
- **Channel-template post-install invocation (D8)**: whether
  `bring-up-local-channel.sh` calls the Flux post-install script directly,
  or whether the Flux post-install is its own top-level script that the
  operator runs after `bring-up-local-channel.sh` succeeds.
- **`source_kind` validator surface (D7)**: whether the validator rejects
  any non-`git` value at schema-validation time (preferred) or whether the
  schema accepts the future `oci` value but the renderer rejects it.

---

**File**: `worktrees/init-102-gitops-substrate/.pipeline/synthesis.md`
