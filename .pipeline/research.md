# INIT-102 Phase 1 Research: GitOps Substrate

Scope: evidence-only research for INIT-102, the GitOps substrate that runs on
top of INIT-101's k3s control cluster.

Non-goal: this document does not design the final implementation. It records
repo facts, upstream contracts, local tool availability, risks, open questions,
and proposal-phase inputs for Flux v2, Kustomize channel overlays, and
SOPS+age bootstrap-only secrets.

## 0. Source Authority

- D8 is the controlling decision for INIT-102. Phase 5 is reset around
  local-as-first-deployment, self-managed k3s everywhere, Flux as the GitOps
  reconciler, SOPS+age as bootstrap-only, Infisical as runtime secrets, and
  channel templates as the environment model. Citation: `DECISIONS.md:176-204`.
- D8 supersedes kind as the Phase 5 local Kubernetes target and supersedes
  SOPS+age as a runtime secret store. Citation: `DECISIONS.md:215-222`.
- D8 also says MinIO bucket-watched Flux is superseded by Git-backed Flux.
  Citation: `DECISIONS.md:229-230`.
- D8 consequence: no VKE module, VKE schema, kind-only harness,
  SOPS-runtime framing, or VKE Crossplane work should merge. Citation:
  `DECISIONS.md:252-260`.
- The environment-agnostic memory says local is a deployment target, not a
  simulation; same code, components, and manifests run locally and remotely;
  per-channel config carries differences. Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/environment-agnostic-stack.md:7-14`.
- That memory says the GitOps layer is Flux reconciling a channel overlay in
  both local and remote channels. Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/environment-agnostic-stack.md:15-20`.
- The same memory explicitly forbids dry-run substitutes, kind-as-VKE
  simulation, local-only verification as a goal, and environment-specific rules
  where channel parameterization can carry the difference. Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/environment-agnostic-stack.md:29-43`.
- It also records the prior mistake: treating secrets as SOPS-only was wrong;
  Infisical is the runtime store. Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/environment-agnostic-stack.md:62-68`.
- The channel-template memory rejects hard `infra/environments/dev`,
  `staging`, and `production` roots and points at
  `infra/templates/platform-channel/`, `infra/channels/<id>/channel.yaml`, and
  a schema as the Phase 5 shape. Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/channel-template-pattern.md:7-8`
  and
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/channel-template-pattern.md:50-56`.
- The channel-template memory specifically says Flux Kustomizations should
  align with channels and that inheritance maps to Kustomize bases/overlays.
  Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/channel-template-pattern.md:67-74`.
- The two-tier architecture memory says the control/platform cluster hosts
  platform controllers, including Flux, and does not host application
  workloads. Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/two-tier-cluster-architecture.md:7-18`.
- The Phase 5 index names INIT-102 as "Flux, Kustomize channel overlays,
  SOPS+age bootstrap-only, real reconciliation in local k3d." Citation:
  `product-strategy/tickets/PHASE_5_INDEX.md:24-31`.
- The Phase 5 operating rules repeat that Flux must reconcile the local
  channel from this repository and that SOPS+age bootstraps only secrets needed
  to start runtime secret management. Citation:
  `product-strategy/tickets/PHASE_5_INDEX.md:96-130`.
- The Phase 5 index archives INIT-009 as reference-only and says Flux,
  Kustomize, and SOPS ideas are salvageable through INIT-102. Citation:
  `product-strategy/tickets/PHASE_5_INDEX.md:150-156`.
- The no-backwards-compatibility convention bans deprecated aliases, dual
  implementations, transitional adapters, and partial migrations. Citation:
  `~/ai/conventions/no-backwards-compatibility.md:1-24`.

## 1. Current Repo State For GitOps

### 1.1 INIT-101 control-cluster substrate

- INIT-101's proposal says the local channel runs k3d, remote channels are
  OpenTofu-managed Vultr Cloud Compute VMs bootstrapped by cloud-init, and the
  done state is a real local k3d cluster with `kubectl get nodes` succeeding.
  Citation:
  `/home/nes/projects/server-manager/worktrees/init-101-k3s-control-cluster/.pipeline/proposal.md:45-76`.
- INIT-101 explicitly leaves Flux to INIT-102, Infisical to INIT-103, and
  Crossplane to INIT-106. Citation:
  `/home/nes/projects/server-manager/worktrees/init-101-k3s-control-cluster/.pipeline/proposal.md:79-90`.
- INIT-101's `infra/` shape includes channel schemas, `local.yaml`,
  `dev.yaml`, `infra/templates/platform-channel/`, local and dev OpenTofu
  roots, `platform-cluster-k3d`, `platform-cluster-vms`, and local bring-up
  scripts. Citation:
  `/home/nes/projects/server-manager/worktrees/init-101-k3s-control-cluster/.pipeline/proposal.md:91-155`.
- Current `infra/README.md` says `infra/` contains Vultr-locked OpenTofu,
  self-managed k3s, channel templates, and local-first deployment scripts.
  Citation: `infra/README.md:5-15`.
- Current `infra/README.md` says required INIT-101 tools are OpenTofu `1.11.5`,
  kubectl `>= 1.31`, Docker `>= 24`, Python `>= 3.10` with `jsonschema` and
  `PyYAML`, and k3d `v5.8.3`. Citation: `infra/README.md:16-29`.
- Current `infra/templates/platform-channel/main.tf` dispatches on
  `cluster_target`: `k3d-local` calls `platform-cluster-k3d`, while
  `vultr-vms` calls network plus `platform-cluster-vms`. Citation:
  `infra/templates/platform-channel/main.tf:5-44`.
- Current `infra/templates/platform-channel/variables.tf` accepts
  `cluster_target` values `k3d-local` and `vultr-vms`, and constrains
  `cluster_distribution` to `k3s`. Citation:
  `infra/templates/platform-channel/variables.tf:6-24`.
- Current `infra/channels/local.yaml` is a k3d-local channel with k3s
  `v1.32.13+k3s1`, one server, one agent, registry `humility-local`, and state
  key `channels/local/terraform.tfstate`. Citation: `infra/channels/local.yaml:1-19`.
- Current `infra/channels/dev.yaml` is a Vultr VM channel with region `ewr`,
  remote kubeconfig path `/root/humility-k3s.yaml`, one `vc2-2c-4gb` server,
  zero agents, and state key `channels/dev/terraform.tfstate`. Citation:
  `infra/channels/dev.yaml:1-27`.
- Current `infra/schemas/platform-channel.schema.json` has no `gitops` block
  and no Flux/SOPS fields. It defines metadata, `cluster`, and `state`.
  Citation: `infra/schemas/platform-channel.schema.json:16-47`.

### 1.2 Current GitOps material in this worktree

- Contrary to the prompt's "no Flux manifests in tree" expectation, the current
  worktree has a 38-file `k8s/` tree. Command evidence: `find k8s -type f |
  wc -l` returned `38` on 2026-04-26.
- That `k8s/` tree is not channel-template-shaped. Its active overlays are
  hard-coded `dev`, `staging`, and `production`, each split into
  `control-cluster` and `app-cluster`. Citation:
  `k8s/tests/test_gitops_foundation.sh:217-248`.
- The `k8s/` tree includes Flux CR objects in `gotk-sync.yaml`, but the source
  URL is a placeholder `ssh://git@example.com/humility/discord.git`. Citation:
  `k8s/clusters/dev/control-cluster/gotk-sync.yaml:1-25`.
- The same placeholder URL appears in staging and production control/app
  cluster roots. Citation:
  `k8s/clusters/staging/control-cluster/gotk-sync.yaml:1-25` and
  `k8s/clusters/production/control-cluster/gotk-sync.yaml:1-25`.
- The current `k8s/` base includes generated ConfigMaps, namespaces, and
  policy markers, but no vendored Flux controller install manifest. Citation:
  `k8s/base/kustomization.yaml:1-7` and
  `k8s/base/controllers/kustomization.yaml:1-11`.
- The current `k8s/` roots include app-cluster paths before INIT-106 creates
  application cluster provisioning. Citation:
  `k8s/clusters/dev/app-cluster/gotk-sync.yaml:1-25`; controlling boundary:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/two-tier-cluster-architecture.md:20-47`.
- The current `k8s/` validation test bans Buildkite direct cluster mutation and
  validates Flux paths, which is conceptually salvageable as harness posture.
  Citation: `k8s/tests/test_gitops_foundation.sh:197-254`.
- The current worktree has no root-level `gitops/` directory. Command evidence:
  `find gitops -maxdepth 3 -type f` returned no files on 2026-04-26.
- The current worktree has no `.sops.yaml` and no `*.enc.yaml` files. Command
  evidence: `find . -name '.sops.yaml' -o -name '*.enc.yaml'` returned no files
  on 2026-04-26.
- Current `.pipeline/` files in this worktree are stale INIT-101 artifacts:
  `.pipeline/proposal.md` is titled "INIT-101 Phase 3 Proposal." Citation:
  `.pipeline/proposal.md:1-4`.

### 1.3 INIT-009 archived GitOps substrate

- The archived INIT-009 worktree is
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate`,
  branch `feat/init-009-gitops-substrate`, HEAD `027b3b6`. Command evidence:
  `git -C ... rev-parse --short HEAD` and `git -C ... log -1 --oneline` on
  2026-04-26.
- INIT-009's proposal was bound to old decisions: local cluster was `kind`,
  active manifests under root-level `gitops/`, SOPS recipients were
  per-channel, and `k8s/` was deleted. Citation:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/.pipeline/proposal.md:26-36`.
- Salvageable shape: INIT-009 proposed Flux on the control cluster,
  channel-aligned Kustomize layout, local Git source for verification, and a
  root-level `gitops/` tree. Citation:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/.pipeline/proposal.md:39-73`.
- Wrong-shaped detail: INIT-009 used kind for local verification, now
  superseded by D8's k3d/k3s requirement. Citation:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/.pipeline/proposal.md:382-390`
  and `DECISIONS.md:215-218`.
- Wrong-shaped detail: INIT-009 used `dev` as the active channel inherited from
  the old INIT-008 control-cluster channel, while INIT-101 now provides
  `local` as the real first deployment target. Citation:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/README.md:10-17`
  and `infra/channels/local.yaml:1-19`.
- Wrong-shaped detail: INIT-009 generated Flux `gotk-components.yaml` with
  source, kustomize, helm, notification, image-reflector, and
  image-automation controllers. Citation:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/bases/flux-system/gotk-components.yaml:1-14`.
- Wrong-shaped detail: INIT-009's SOPS sample contained a placeholder age
  recipient and an unencrypted placeholder Secret with empty `stringData`.
  Citation:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/secrets/dev/.sops.yaml:17-24`
  and
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/secrets/dev/bootstrap-creds.enc.yaml:1-10`.
- Salvageable SOPS custody notes: public recipient committed in `.sops.yaml`,
  private key stored outside the repo, `SOPS_AGE_KEY_FILE` used for local
  decryption, and add/remove/rotate runbook. Citation:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/secrets/dev/README.md:7-35`.
- Discard the SOPS-as-runtime framing. D8 says SOPS+age is bootstrap-only and
  Infisical owns runtime secrets. Citation: `DECISIONS.md:196-198` and
  `DECISIONS.md:219-222`.

## 2. Flux v2 Installation Contract

### 2.1 Flux components and minimum controller set

- Flux documents four GitOps Toolkit controller families: source-controller,
  kustomize-controller, helm-controller, and notification-controller. Citation:
  https://fluxcd.io/flux/components/
- source-controller is the API for sources such as Git repositories, Helm
  repositories, Helm charts, OCI repositories, and Buckets. Citation:
  https://fluxcd.io/flux/components/source/
- kustomize-controller specializes in running continuous delivery pipelines for
  infrastructure and workloads defined with Kubernetes manifests and assembled
  with Kustomize. Citation: https://fluxcd.io/flux/components/kustomize/
- The `Kustomization` API states that `.spec.interval` is required and defines
  the interval at which reconciliation is performed. Citation:
  https://fluxcd.io/flux/components/kustomize/kustomizations/
- The `GitRepository` API states that `.spec.interval` is required and defines
  how often the source is reconciled. Citation:
  https://fluxcd.io/flux/components/source/gitrepositories/
- INIT-102's minimum functional loop for raw manifests is source-controller
  plus kustomize-controller: source-controller fetches the artifact, and
  kustomize-controller applies a `Kustomization` path from that source.
  Evidence chain: source-controller GitRepository docs plus kustomize-controller
  Kustomization docs above.
- helm-controller is needed for `HelmRelease` reconciliation, but INIT-102
  explicitly excludes Helm/application workloads; later initiatives may add
  Helm sources. Citation for Flux Helm API:
  https://fluxcd.io/flux/components/helm/
- notification-controller owns alerting/webhook receiver surfaces. INIT-117 owns
  observability/notifications in the Phase 5 index. Citation:
  `product-strategy/tickets/PHASE_5_INDEX.md:45` and
  https://fluxcd.io/flux/components/notification/
- OCIRepository is a source-controller CRD and can be used as a source artifact
  for Kubernetes manifests, but Helm usage is separate and later. Citation:
  https://fluxcd.io/flux/components/source/ocirepositories/

### 2.2 `flux install` versus `flux bootstrap`

- Flux installation docs expose `flux install` for installing Flux controllers
  on a cluster. Citation: https://fluxcd.io/flux/installation/
- The `flux install` command can export installation manifests instead of
  applying them, allowing generated controller YAML to be committed and
  reconciled. Citation: https://fluxcd.io/flux/cmd/flux_install/
- Flux bootstrap docs describe bootstrap as installing Flux on a cluster and
  configuring Flux to manage itself from a Git repository. Citation:
  https://fluxcd.io/flux/installation/bootstrap/
- The `flux bootstrap git` command is the generic bootstrap variant for a Git
  repository. Citation: https://fluxcd.io/flux/cmd/flux_bootstrap_git/
- Evidence implication: `flux bootstrap` combines initial cluster install with
  Git repository wiring, while `flux install --export` separates controller
  manifest generation from source/root `GitRepository` and `Kustomization`
  objects.
- Channel-template implication for proposal phase: if channel overlays own all
  manifests in-tree, `flux install --export` gives a more explicit artifact
  boundary; if the bootstrap CLI owns initial source/root creation, bootstrap
  must be constrained so it does not rewrite repo layout outside the channel
  template.

### 2.3 Flux CRDs and fields relevant to INIT-102

- `GitRepository` supports Git sources, including `url`, `ref`, `interval`,
  `secretRef`, and suspend behavior. Citation:
  https://fluxcd.io/flux/components/source/gitrepositories/
- Flux Git authentication docs cover SSH deploy keys, HTTPS basic auth/token,
  and provider-specific bootstrap flows. Citation:
  https://fluxcd.io/flux/installation/bootstrap/github/
  and https://fluxcd.io/flux/components/source/gitrepositories/#secret-reference
- `Kustomization` supports `sourceRef`, `path`, `interval`, `prune`, `wait`,
  `timeout`, `dependsOn`, and decryption settings. Citation:
  https://fluxcd.io/flux/components/kustomize/kustomizations/
- `OCIRepository` provides source artifacts from OCI registries and supports
  interval-driven reconciliation. Citation:
  https://fluxcd.io/flux/components/source/ocirepositories/
- `Bucket` sources exist, but D8 explicitly supersedes MinIO bucket-watched Flux
  with Git-backed Flux. Citation: `DECISIONS.md:229-230` and
  https://fluxcd.io/flux/components/source/buckets/
- Reconciliation cadence is object-specific. The current stale `k8s/` tree uses
  `GitRepository.spec.interval: 1m0s` and `Kustomization.spec.interval: 10m0s`.
  Citation: `k8s/clusters/dev/control-cluster/gotk-sync.yaml:6-24`.
- INIT-009's proposal used `GitRepository` `1m` and root `Kustomization` `5m`.
  Citation:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/.pipeline/proposal.md:280-291`.
- Flux version pinning evidence: GitHub API reported latest Flux v2 release
  `v2.8.6`, published 2026-04-21. Citation:
  https://github.com/fluxcd/flux2/releases/tag/v2.8.6.
- Flux-generated controller manifests carry controller image tags. INIT-009's
  generated manifest labels `app.kubernetes.io/version: v2.8.0` and controller
  components in comments. Citation:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/bases/flux-system/gotk-components.yaml:1-14`.

## 3. Repo Layout For Channel Overlays

- Kustomize's Kubernetes documentation describes a `kustomization.yaml` with
  `resources`, `configMapGenerator`, `secretGenerator`, and patches to customize
  Kubernetes objects. Citation:
  https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization
- The same documentation describes bases and overlays: a base can be reused by
  multiple overlays, and overlays can customize names, labels, images, replicas,
  and patches. Citation:
  https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/#bases-and-overlays
- The channel-template memory says channel inheritance maps to Kustomize
  bases/overlays. Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/channel-template-pattern.md:69-74`.
- INIT-009's salvageable layout used root-level `gitops/`, `bases/`,
  `channels/<channel-id>/`, and `secrets/<channel-id>/`. Citation:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/.pipeline/proposal.md:112-155`.
- INIT-009's README describes `bases/` as reusable Kustomize bases and
  `channels/` as channel overlays. Citation:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/README.md:55-69`.
- Current stale `k8s/` has a base/overlay/root shape, but the overlay keys are
  environment names (`dev`, `staging`, `production`) rather than channel ids.
  Citation: `k8s/tests/test_gitops_foundation.sh:217-248`.
- Current stale `k8s/` also includes `app-cluster` roots even though
  app-cluster provisioning is later INIT-106. Citation:
  `k8s/clusters/dev/app-cluster/kustomization.yaml:1-4` and
  `product-strategy/tickets/PHASE_5_INDEX.md:34`.
- Repo-layout evidence therefore supports these proposal-phase questions:
  where to place the accepted GitOps root (`gitops/` versus reshaped `k8s/`);
  how to name overlays by channel id; and whether the accepted INIT-102 scope
  contains only `local` control-cluster material or also a remote `dev` plan
  overlay.
- Naming evidence from INIT-101: active channel ids are `local` and `dev`.
  Citation: `infra/channels/local.yaml:1-7` and `infra/channels/dev.yaml:1-7`.
- Path evidence from Flux: a Flux `Kustomization` points to a path within the
  source artifact using `.spec.path`. Citation:
  https://fluxcd.io/flux/components/kustomize/kustomizations/
- Per-channel Flux Kustomization evidence: the current stale `k8s/` CR uses
  path `./k8s/clusters/dev/control-cluster/manifests`, proving the existing
  repo already expects one path per root. Citation:
  `k8s/clusters/dev/control-cluster/gotk-sync.yaml:17-24`.

## 4. SOPS+age Bootstrap-Only Contract

### 4.1 SOPS and age mechanics

- SOPS supports age recipients and stores encryption metadata in the encrypted
  file. Citation: https://github.com/getsops/sops#encrypting-using-age.
- SOPS supports `.sops.yaml` creation rules, including path-based matching and
  configured recipients. Citation:
  https://github.com/getsops/sops#using-sops-yaml-conf-to-select-kms-pgp-and-age-for-new-files.
- SOPS supports `encrypted_regex`, allowing encryption to be scoped to YAML
  fields such as `data` and `stringData`. Citation:
  https://github.com/getsops/sops#encrypting-only-parts-of-a-file.
- age provides `age-keygen` to generate age key pairs. Citation:
  https://github.com/FiloSottile/age.
- SOPS reads age private keys through `SOPS_AGE_KEY_FILE` or SOPS age key
  configuration. Citation: https://github.com/getsops/sops#encrypting-using-age.
- Flux SOPS integration requires a Kubernetes Secret in the same namespace as
  the Kustomization, containing the age identity file, and the Kustomization
  references it through `.spec.decryption.secretRef`. Citation:
  https://fluxcd.io/flux/guides/mozilla-sops/
- Flux docs show creating the SOPS age secret with `kubectl create secret
  generic sops-age --namespace=flux-system --from-file=age.agekey=...`.
  Citation: https://fluxcd.io/flux/guides/mozilla-sops/
- Flux docs show `spec.decryption.provider: sops` and `secretRef.name:
  sops-age` on a `Kustomization`. Citation:
  https://fluxcd.io/flux/guides/mozilla-sops/

### 4.2 Bootstrap-only boundary

- D8 says SOPS+age remains bootstrap-only and Infisical is the runtime secret
  store. Citation: `DECISIONS.md:196-198`.
- Phase 5 completion criteria say SOPS+age bootstraps only secrets needed to
  start runtime secret management, and Infisical owns runtime secrets. Citation:
  `product-strategy/tickets/PHASE_5_INDEX.md:126-130`.
- INIT-103 owns Infisical runtime secret store, including Infisical,
  Infisical Operator, InfisicalSecret CRDs, RBAC, and runtime secret ownership.
  Citation: `product-strategy/tickets/PHASE_5_INDEX.md:31`.
- Enforcement is by file content and ownership, not by SOPS itself. SOPS can
  encrypt any YAML matched by `.sops.yaml`; INIT-102 must define which
  bootstrap-tier files are allowed to exist.
- Bootstrap-tier examples from the prompt: Flux Git deploy key and age
  decryption key delivery. Boundary evidence: runtime app secrets are outside
  INIT-102 and assigned to INIT-103. Citation:
  `product-strategy/tickets/PHASE_5_INDEX.md:30-31`.
- INIT-009's `gitops/secrets/dev/bootstrap-creds.enc.yaml` is not usable
  evidence for real secret content because it contains placeholder empty
  `stringData`. Citation:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/secrets/dev/bootstrap-creds.enc.yaml:1-10`.

### 4.3 Key lifecycle evidence

- Key generation procedure evidence from age/SOPS: operator runs `age-keygen`
  to generate a private identity and extracts/records the public recipient for
  `.sops.yaml`. Citation: https://github.com/FiloSottile/age and
  https://github.com/getsops/sops#encrypting-using-age.
- INIT-009's custody notes stored private keys at
  `~/.config/sops/age/<channel>.txt` and committed public recipients in the
  channel `.sops.yaml`. Citation:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/secrets/dev/README.md:7-19`.
- INIT-009's rotation notes add a new recipient, run `sops updatekeys`, remove
  the old recipient, and update keys again. Citation:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/secrets/dev/README.md:27-35`.
- Delivery chicken-and-egg: the cluster must receive the age private key as a
  Kubernetes Secret before Flux can decrypt encrypted bootstrap files. Flux docs
  explicitly create the secret outside Flux before SOPS decryption works.
  Citation: https://fluxcd.io/flux/guides/mozilla-sops/.
- This private-key Secret is itself not committed as cleartext. It is an
  operator/bootstrap delivery action; the proposal phase must decide whether
  that delivery is manual `kubectl create secret generic`, a Flux CLI helper,
  or a channel-template post-install step.

## 5. Local-First GitOps

### 5.1 Hard question

- Local-as-first-deployment requires Flux running in local k3d to reconcile a
  real manifest from a source it can reach. Citation:
  `~/.claude3/projects/-home-nes-projects-server-manager/memory/environment-agnostic-stack.md:45-60`.
- The local channel is `k3d-local`; it is not a dry-run or render-only target.
  Citation: `infra/channels/local.yaml:8-15` and `infra/README.md:12-15`.
- Flux `GitRepository` source URLs are fetched by source-controller running
  inside the cluster, not by the operator's local shell. Citation:
  https://fluxcd.io/flux/components/source/gitrepositories/.
- The inner loop is therefore determined by how a k3d cluster sees the working
  Git repository.

### 5.2 Options

- Option A: Point Flux at GitHub or another hosted Git endpoint. Evidence:
  Flux first-class bootstrap providers include GitHub, and GitRepository can use
  HTTPS or SSH auth. Citation:
  https://fluxcd.io/flux/installation/bootstrap/github/ and
  https://fluxcd.io/flux/components/source/gitrepositories/.
- Option A tradeoff: every local reconciliation requires commit/push or a
  hosted branch update before Flux can see changes. This conflicts with the
  prompt's concern about slow GitHub round-trips for local iteration.
- Option B: Run a local Git server, either in-cluster or on the host with k3d
  networking. Evidence: Flux GitRepository only needs a reachable Git URL;
  INIT-009's bootstrap script used an in-cluster `git daemon` service at
  `git://git-local.git-system.svc.cluster.local/server-manager.git`. Citation:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/scripts/bootstrap-flux.sh:4-24`
  and
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/channels/dev/patches/flux-source-local.yaml:1-7`.
- Option B tradeoff: it adds a local Git service lifecycle, branch/bundle
  seeding, and trust/auth decisions. The evidence also shows it avoids GitHub,
  Vultr, real DNS, and hosted Git for proof. Citation:
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/scripts/bootstrap-flux.sh:4-9`.
- Option C: Use Flux `OCIRepository` with a local OCI registry. Evidence:
  source-controller supports OCIRepository sources, and k3d can create or use
  local registries. Citations:
  https://fluxcd.io/flux/components/source/ocirepositories/ and
  https://k3d.io/stable/usage/registries/.
- Option C tradeoff: D8 says Git-backed Flux, so OCI may be acceptable as a
  source-controller mechanism only if the proposal treats Git as authoritative
  and OCI as a local artifact transport. Citation: `DECISIONS.md:229-230`.
- Option D: Mount the local repo path into source-controller. Evidence:
  source-controller's documented source APIs are GitRepository, OCIRepository,
  Bucket, HelmRepository, and HelmChart, not arbitrary mounted host paths.
  Citation: https://fluxcd.io/flux/components/source/.
- Option D tradeoff: it depends on controller deployment mutation and host-path
  coupling; no upstream Flux source API evidence supports it as a normal
  GitOps source.

### 5.3 Research recommendation for proposal phase

- Recommended local-first source approach: local Git server, preferably
  in-cluster or host-reachable from k3d, seeded from the current worktree.
- Rationale: it preserves GitRepository semantics, keeps Git as the source
  type, avoids GitHub push round-trips, and is already partially prototyped in
  archived INIT-009. Citations:
  https://fluxcd.io/flux/components/source/gitrepositories/ and
  `/home/nes/projects/server-manager/worktrees/init-009-gitops-substrate/gitops/scripts/bootstrap-flux.sh:4-24`.
- This recommendation is not final design. Proposal phase still must choose
  the concrete service lifecycle, auth posture, branch naming, and cleanup
  behavior, and must verify it in k3d rather than kind.

## 6. Channel-Template Integration

- Current `infra/templates/platform-channel/main.tf` is the dispatch point for
  channel cluster targets. Citation: `infra/templates/platform-channel/main.tf:1-44`.
- Current template variables do not include GitOps source URL, branch/ref,
  manifest path, Flux version, SOPS age Secret name, or reconciliation interval.
  Citation: `infra/templates/platform-channel/variables.tf:1-120`.
- Current source schema has no `gitops` field. Citation:
  `infra/schemas/platform-channel.schema.json:16-47`.
- Current resolved/channel generator must therefore change if INIT-102 wants
  per-channel GitOps settings to be validated and emitted into roots. Evidence:
  generator/resolver ownership in INIT-101 layout: `infra/README.md:31-75`.
- Possible schema additions for proposal consideration: `gitops.git_url`,
  `gitops.git_ref`, `gitops.path`, `gitops.source_kind`, `gitops.interval`,
  `gitops.retry_interval`, `gitops.kustomization_name`,
  `gitops.kustomization_namespace`, `gitops.sops_age_secret_name`, and
  `gitops.decryption_secret_namespace`.
- Boundary concern: the `gitops` block should carry Flux source and bootstrap
  decryption metadata only. Runtime secret provider fields belong to INIT-103
  Infisical, not INIT-102. Citation:
  `product-strategy/tickets/PHASE_5_INDEX.md:30-31`.
- Integration shape evidence from INIT-101: local bring-up creates the cluster
  and kubeconfig, while INIT-101 anti-scope names GitOps reconciliation and
  Flux installation as INIT-102. Citation: `infra/README.md:84-109` and
  `infra/README.md:170-181`.
- Proposal-phase question: Flux installation could be modeled as a new
  OpenTofu-adjacent module/post-install step or as a separate script invoked
  after cluster bring-up. Evidence only: INIT-101 uses scripts for local k3d
  lifecycle and modules for cluster resources. Citation:
  `infra/README.md:84-109` and
  `infra/templates/platform-channel/main.tf:15-26`.
- Terraform/OpenTofu cannot safely hide user-visible cluster mutations in this
  repo without explicit contracts; however INIT-102's visible effect is local
  cluster mutation, not Discord Tier 3. Citation for local cluster done state:
  `product-strategy/tickets/PHASE_5_INDEX.md:98-130`.

## 7. Toolchain Check

### 7.1 Local availability on 2026-04-26

- `flux`: not installed. Command evidence: `flux --version` returned
  `command not found`.
- `sops`: not installed. Command evidence: `sops --version` returned
  `command not found`.
- `age`: not installed. Command evidence: `age --version` returned
  `command not found`.
- `age-keygen`: not installed. Command evidence: `age-keygen --version`
  returned `command not found`.
- `tofu`: installed as `/home/nes/.local/bin/tofu`; `tofu version` reports
  OpenTofu `v1.11.5`.
- `kubectl`: installed as `/usr/local/bin/kubectl`; `kubectl version
  --client=true` reports client `v1.34.1` and embedded Kustomize `v5.7.1`.
- standalone `kustomize`: not installed. Command evidence: `kustomize version`
  returned `command not found`.
- `k3d`: installed as `/home/nes/.local/bin/k3d`; `k3d version` reports
  `v5.8.3` and default k3s `v1.31.5-k3s1`.
- Docker: installed as `/usr/bin/docker`; `docker --version` reports
  `29.4.0`.
- INIT-101's k3d installer check passes: `bash infra/scripts/install-cluster-tools.sh
  --check --no-color` returned `OK: k3d v5.8.3`.

### 7.2 Version pins to consider

- Flux latest official GitHub release on 2026-04-26 is `v2.8.6`, published
  2026-04-21. Citation: https://github.com/fluxcd/flux2/releases/tag/v2.8.6.
- SOPS latest official GitHub release on 2026-04-26 is `v3.12.2`, published
  2026-03-18. Citation: https://github.com/getsops/sops/releases/tag/v3.12.2.
- age latest official GitHub release on 2026-04-26 is `v1.3.1`, published
  2025-12-28. Citation: https://github.com/FiloSottile/age/releases/tag/v1.3.1.
- Kustomize latest official standalone release on 2026-04-26 is
  `kustomize/v5.8.1`, published 2026-02-09. Citation:
  https://github.com/kubernetes-sigs/kustomize/releases/tag/kustomize/v5.8.1.
- INIT-101 pins k3d `v5.8.3` in its installer. Citation:
  `infra/scripts/install-cluster-tools.sh:1-5`.
- INIT-101 required tools still apply: OpenTofu, kubectl, Docker, Python,
  jsonschema/PyYAML, and k3d. Citation: `infra/README.md:16-29`.

## 8. Known Risks And Open Questions

### 8.1 BLOCKS_PROPOSAL

- Local source decision: proposal cannot be precise without choosing between
  GitHub round-trip, local Git server, OCI artifact source, or a controller
  mount hack. Evidence and tradeoffs are in Section 5.
- Accepted GitOps directory disposition: proposal must decide whether to delete
  the stale `k8s/` tree, replace it with root-level `gitops/`, or reshape
  `k8s/` into channel terminology. Current evidence: 38 stale files in `k8s/`,
  no `gitops/`, no `.sops.yaml`.
- Flux component set: proposal must decide whether INIT-102 installs only
  source-controller and kustomize-controller or includes the default
  helm-controller/notification-controller set. Evidence: Flux components docs
  plus INIT-102 anti-scope excluding Helm apps and notifications.
- Channel schema additions: proposal must define whether GitOps config lives in
  `infra/channels/*.yaml` and what fields are INIT-102-owned versus
  INIT-103-owned.

### 8.2 BLOCKS_IMPLEMENTATION

- Toolchain installer must add pinned `flux`, `sops`, `age`, and `age-keygen`
  because none are installed locally.
- SOPS bootstrap must solve the age private-key delivery chicken-and-egg before
  any encrypted bootstrap file can reconcile.
- Local k3d cluster availability must be verified before Flux reconciliation
  tests can run. INIT-101's cluster-mode harness exists, but this research did
  not create or mutate a cluster.
- The chosen local Git source must be reachable from inside k3d and must be
  seedable from the current worktree/branch without requiring GitHub pushes.
- Any generated Flux controller manifest must be pinned to a concrete Flux
  release and checked against the toolchain version.

### 8.3 INFORMATIONAL

- Helm controller can be deferred unless a later INIT needs `HelmRelease`.
  INIT-102 can document that Helm CRDs/controllers are not part of the minimum
  raw-manifest loop.
- Notification controller can be deferred to INIT-117, which owns
  observability. Citation: `product-strategy/tickets/PHASE_5_INDEX.md:45`.
- Multi-tenancy and Flux RBAC boundaries can be deferred to INIT-115/116 unless
  Flux's bootstrap permissions create an immediate security problem. Citation:
  `product-strategy/tickets/PHASE_5_INDEX.md:43-44`.
- Runtime secrets must not leak into SOPS just because SOPS is available.
  The boundary is ownership/content review, not a technical limitation in SOPS.
- The stale `k8s/` tree's Buildkite mutation guard is useful evidence for a
  future harness, but its environment triad is wrong-shaped. Citation:
  `k8s/tests/test_gitops_foundation.sh:197-254`.

## 9. Suggested Slice Decomposition Sketch

- SLICE-102.01: Toolchain installer. Evidence target: pinned `flux`, `sops`,
  `age`, `age-keygen`, plus checks for existing INIT-101 tools.
- SLICE-102.02: Accepted GitOps repo layout and Flux base manifests. Evidence
  target: remove or quarantine stale `k8s/`, create channel-aligned layout, and
  pin Flux controller manifest version.
- SLICE-102.03: SOPS+age bootstrap-only procedure. Evidence target:
  `.sops.yaml`, encrypted bootstrap-tier sample/fixture, age key custody docs,
  and age private-key Secret delivery path.
- SLICE-102.04: Channel-template integration. Evidence target: channel schema
  fields for Flux source/path/ref/version/decryption secret and generated
  per-channel config.
- SLICE-102.05: Local-first GitOps loop. Evidence target: Flux in real local
  k3d reconciles a real manifest from the chosen local Git source.
- SLICE-102.06: Harness and handoff docs. Evidence target: assertions for Flux
  health, source readiness, Kustomization readiness, reconciled test manifest,
  and clear INIT-103 Infisical boundary.

## 10. Evidence Summary For Proposal Phase

- Highest-priority proposal item 1: choose the local source mechanism. The
  research recommendation is a local Git server because it preserves
  GitRepository semantics and avoids GitHub round-trips.
- Highest-priority proposal item 2: decide the accepted repo layout and stale
  `k8s/` disposition. Current state has stale hard-environment GitOps material
  but no accepted channel-aligned `gitops/` layout.
- Highest-priority proposal item 3: define the bootstrap-secret boundary and
  age key delivery. Flux cannot decrypt SOPS files until an age private key
  Secret exists in-cluster.
- Toolchain availability summary: missing `flux`, `sops`, `age`, and
  `age-keygen`; available OpenTofu `1.11.5`, kubectl `1.34.1` with embedded
  Kustomize `5.7.1`, k3d `5.8.3`, and Docker `29.4.0`; standalone Kustomize
  absent.
- Recommended local-first GitOps source approach: local Git server seeded from
  the current worktree. Rationale: Git-backed Flux remains the source model,
  k3d can reach an in-cluster or host-exposed endpoint, and archived INIT-009
  already tested the shape conceptually with `git://git-local...`; proposal
  must redo it against k3d and current channel names.
