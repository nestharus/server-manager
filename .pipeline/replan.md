# Phase 5 Re-plan: Environment-Agnostic, Local-As-First-Deployment

Prepared: 2026-04-26
Source sessions and memory corrections referenced: 2026-04-25
Worktree: `/home/nes/projects/server-manager/worktrees/phase-5-replan`
Output pair: `.pipeline/replan.md` and `PHASE_5_INDEX.md`

This artifact replaces the wrong-shaped 9-INIT Phase 5 plan with an
environment-agnostic plan. It is research plus synthesis for user review, not
a per-initiative proposal and not implementation approval.

## Source Register

### Governing memory and workflow

- `memory/environment-agnostic-stack.md`: local is a deployment target, not a
  simulation; same components run local and remote; channel config carries
  provider and endpoint differences.
- `memory/two-tier-cluster-architecture.md`: preserve control cluster plus app
  cluster separation.
- `memory/channel-template-pattern.md`: channels, inheritance, exposure, tenant,
  and ephemeral-child concepts replace hard environment roots.
- `memory/platform-stack.md`: Vultr, OpenTofu, Buildkite, Flux, Authentik,
  OPAL/Cedar, Pomerium are locked, except the VKE-specific cluster decision is
  now superseded by the later environment-agnostic memory.
- `memory/discord-registration.md`: the Discord bot already exists in Humility
  and beta guilds; bot registration is not a pending task.
- `memory/secrets-and-domains.md`: domains and Cloudflare credentials exist;
  credentials must not be committed.
- `memory/feedback-escalation-bar.md`: technical implementation decisions are
  made here and documented; user input is reserved for value-level gates.
- `~/ai/workflows/research.md` and `~/ai/workflows/roadmap.md`: this is a
  roadmap revision artifact with evidence and recommendations before
  per-INIT pipeline restart.
- `~/ai/conventions/no-backwards-compatibility.md`: wrong-shaped work is
  deleted from the main path rather than shimmed.
- `~/ai/conventions/no-deferred-stubs.md`: every initiative must deploy real
  local-channel components as its done state.

### Current repository and shipped work

- `../init-017-crossplane/.pipeline/prior-decisions-audit.md`: 70-decision
  audit; row IDs cited below as `AUD-*`.
- `../init-008-platform-bootstrap/.pipeline/proposal.md`: shipped INIT-008
  proposal and slice plan.
- `../init-009-gitops-substrate/.pipeline/proposal.md`: shipped INIT-009
  proposal and slice plan.
- `../init-017-crossplane/.pipeline/research.md` and
  `../init-017-crossplane/.pipeline/synthesis.md`: paused, wrong-shaped
  Crossplane/VKE work.
- `DECISIONS.md`, `infra/README.md`, `plans/platform-decisions-overlay.md`.
- Surviving `plans/proposals/*.md` and `plans/research/*.md`, especially
  `platform-bootstrap.md`, `gitops-foundation.md`,
  `app-cluster-provisioning.md`, `self-hosted-s3.md`,
  `buildkite-capabilities.md`, `database-stack.md`, and
  `pomerium-smallstep.md`.

### Deleted-history samples

- `5781727`: `plans/legacy/auth-v5-index.md`, `expansion-plan-index.md`,
  `gitops-index.md`; strongest evidence for Infisical, Authentik,
  OPAL/Cedar, Pomerium, break-glass, observability, and Cloudflare edge
  history.
- `be89f7b`: `plans/legacy/platform-v2.md`; broad legacy platform blueprint
  with Infisical, MinIO, Harbor, Linkerd, VictoriaMetrics, Elastic, Kafka,
  StackStorm, Crossplane, Flux, and VKE.
- `4e2a70c`: `plans/unified-platform-index.md`; merged index that normalized
  some legacy choices but later became stale where the user ratified Vultr,
  Crossplane, Flux, Buildkite, Authentik, OPAL/Cedar, Pomerium, and channel
  templates.
- `775ef4c`: `plans/initiative-map.md`; strongest legacy normalization map for
  Buildkite, Flux, object storage, two-tier topology, and anti-import of
  Dagger/JFrog/MinIO claim-bus/bucket-watched Flux.

## 1. Principle Statement

The governing constraint for Phase 5 is:

**Local is a deployment target. It is not a simulation, renderer, dry-run
mode, or exception path.**

The Phase 5 stack must run the same components locally and remotely. The local
channel is simply the first concrete channel. Remote channels are later
channel declarations with different provider endpoints, credentials, resource
sizing, DNS provider, and TLS issuer configuration. The manifests, controllers,
operators, app images, policies, and runtime contracts must remain the same.

This changes the meaning of Phase 5. The old wording drifted toward "local
verification only" and then tried to reconcile a remote-only managed-Kubernetes
decision with local-only checks. That was the framing error. If local is a
deployment target, then the stack cannot choose a remote-only Kubernetes
substrate such as VKE and then bolt on a local exception. The Kubernetes
distribution itself must have a local and remote form. The chosen distribution
is self-managed k3s everywhere: k3d for the local channel and k3s installed by
cloud-init on Vultr Cloud Compute VMs for remote channels.

The rule is stricter than "the same conceptual architecture." It means the
same component classes run:

- Kubernetes: k3s locally and remotely.
- Cluster fleet: Crossplane locally and remotely.
- GitOps: Flux locally and remotely.
- Bootstrap secrets: SOPS+age locally and remotely, only for the
  chicken-and-egg bootstrap path.
- Runtime secrets: Infisical locally and remotely.
- Object storage: S3-compatible API locally and remotely, MinIO locally and
  Vultr Object Storage remotely.
- TLS: cert-manager locally and remotely, with step-ca issuer locally and
  ACME/Let's Encrypt remotely.
- DNS: DNS controller shape locally and remotely, with CoreDNS/local zone
  locally and Cloudflare/ExternalDNS remotely.
- Ingress: the same gateway/controller locally and remotely.
- Database: CloudNativePG locally and remotely.
- Auth: Authentik, OPAL/Cedar, and Pomerium locally and remotely.
- CI/CD: Buildkite locally and remotely, with different agent placement only.
- Observability: the same metrics, logs, traces, dashboards, and alerting
  stack locally and remotely.

Channels are the parameterization boundary. A channel says which target type it
uses (`local` or `remote`), which S3 endpoint it uses, which DNS provider it
uses, which TLS issuer it uses, where Infisical is reachable, what Buildkite
agent queue applies, which Discord guild identity is active, and which
resource sizing is allowed. A channel does not change the architecture.

This preserves the two-tier architecture from the memory record but corrects
the substrate. A remote deployment still has a control cluster and app
clusters. The remote control cluster is created by OpenTofu as Vultr VMs plus
cloud-init k3s bootstrap; Crossplane running on the control cluster provisions
remote app-cluster claims as additional k3s-on-VM clusters. The local channel
uses k3d as the k3s control cluster; local app-cluster semantics are handled as
a real local deployment target, not as a fake provider. The local channel may
treat the local k3d cluster as the only cluster until a per-INIT proposal
proves a clean local multi-cluster k3d path is necessary, but Crossplane, Flux,
Infisical, cert-manager, and workloads still run for real.

This also preserves the channel-template memory. Hard `dev`, `staging`, and
`production` environment roots are not revived under new names. `local`,
`internal`, `customer`, and ephemeral children are channel definitions with
exposure, tenant, inheritance, and provider/endpoint config.

There are no "local special exceptions." There are local channel values. If a
component cannot run locally in a meaningful way, it is the wrong component for
Phase 5 unless the asymmetry is fundamental and explicitly isolated at an
external-provider boundary. The expected genuine asymmetries are limited to
external providers: Cloudflare versus local DNS, Let's Encrypt versus local CA,
Vultr Object Storage versus MinIO, and Buildkite agent placement. Those are
endpoint/provider differences, not architectural exceptions.

Every initiative below must deploy a real component into the local channel as
part of its done state. No initiative is allowed to finish with only rendered
YAML, placeholder directories, stub providers, fake secrets, or a note that
the real system happens later.

## 2. What We Throw Away

### INIT-008 shipped work

Wrong-shaped branch and commit reference:

- Branch: `feat/init-008-platform-bootstrap`
- Current head observed: `9f7090f`
- Proposal: `../init-008-platform-bootstrap/.pipeline/proposal.md`
- Shipped commits include: `a66d39f` through `9f7090f`

Reusable:

- The channel-template direction is still valuable. The shipped work moved
  away from `infra/environments/{dev,staging,production}/` toward
  `infra/channels/<id>.yaml`, generated channel inputs, a resolver, fixtures,
  and a local validation harness. This respects `channel-template-pattern.md`
  and audit rows `AUD-06`, `AUD-14`, `AUD-60`, and `AUD-61`.
- The no-compatibility cleanup posture is reusable. INIT-008 deleted old roots
  instead of keeping wrappers, which aligns with
  `no-backwards-compatibility.md`.
- The remote-state handoff thinking is partially reusable: object-storage
  remote state, no committed credentials, operator handoff, and explicit state
  keying remain useful. This maps to `AUD-05` and the Vultr/Object Storage
  research.
- The validation-harness shape is reusable: scripts that resolve channel YAML,
  generate derived inputs, assert no committed secrets, and run local validation
  are still the right style.
- The OpenTofu provider constraint and Vultr hosting decision remain directionally
  valid at the cloud-provider layer (`AUD-01`, `AUD-02`), but the cluster
  resource target changes from VKE to Vultr Cloud Compute VMs running k3s.

Wrong-shaped and replaced:

- The VKE module and VKE control-cluster target are replaced. A managed
  Kubernetes service that cannot run locally as the same distribution violates
  `environment-agnostic-stack.md`. This supersedes the VKE-specific reading in
  `platform-stack.md`, D7, and audit rows `AUD-03`, `AUD-22`, `AUD-59`, and
  `AUD-67`.
- The `dev` channel as a remote Vultr/VKE control cluster is replaced by a
  local channel whose first target is k3d. Remote channels can still be Vultr,
  but as Vultr VMs plus k3s, not VKE.
- The old state of "Phase 5 local-only, no deployment" is replaced by "local
  deployment first." We no longer accept `tofu validate` or `kubectl kustomize`
  as the end state for components that are supposed to run.
- Any VKE-specific channel fields, provider semantics, and node-pool-only
  surface are replaced by k3s target config: local k3d settings and remote VM
  plus cloud-init settings.
- Any documentation that says INIT-008 produces a VKE control cluster is
  wrong-shaped for the main path.

Disposition:

- Preserve branch `feat/init-008-platform-bootstrap` as a reference branch.
- Do not merge its VKE module, VKE roots, VKE channel schema, or
  VKE-oriented docs into the corrected main path.
- Reuse concepts through fresh INIT-101 work only after the proposal phase
  maps them to self-managed k3s.

### INIT-009 shipped work

Wrong-shaped branch and commit reference:

- Branch: `feat/init-009-gitops-substrate`
- Current head observed: `027b3b6`
- Proposal: `../init-009-gitops-substrate/.pipeline/proposal.md`
- Shipped commits include: `ad3f040` through `027b3b6`

Reusable:

- Flux remains canonical (`AUD-11`, `AUD-12`) and respects
  `platform-decisions-overlay.md`.
- The root-level `gitops/` directory is the right main authority if old `k8s/`
  paths are deleted rather than shimmed (`AUD-14`, `AUD-60`, `AUD-61`).
- Kustomize bases plus channel overlays remain the right GitOps shape. They
  respect `channel-template-pattern.md`.
- Per-channel SOPS+age recipients are still useful, but only for bootstrap
  secrets (`AUD-13`).
- The local verification harness concept is reusable, but it must become a
  k3d local deployment harness, not a kind-only verifier.
- The empty handoff-base pattern can survive only where the owning initiative
  is scheduled and the base is explicitly a contract seam, not a silent TODO.

Wrong-shaped and replaced:

- The proposal binds local cluster verification to `kind`. That violates the
  corrected k3s-everywhere principle. Local Kubernetes must be k3d because it
  runs k3s.
- The work was framed as "local verification" rather than "local channel
  deployment." Every Flux/SOPS/Kustomize acceptance criterion must be upgraded
  from render/check to actual reconciliation in the local channel.
- Any wording that allows SOPS+age to be interpreted as the runtime secret
  store is wrong. SOPS+age remains bootstrap-only; Infisical owns runtime
  secrets (`AUD-37`, `AUD-38`, `AUD-62`).
- Any GitOps layout that assumes the control cluster is VKE must be revised to
  target k3s.
- Any app-cluster handoff that assumes VKE or stubbed local provider semantics
  must be removed.

Disposition:

- Preserve branch `feat/init-009-gitops-substrate` as a reference branch.
- Salvage Flux/Kustomize/channel-overlay/SOPS-bootstrap/harness ideas through
  fresh INIT-102.
- Delete or rewrite kind-specific and VKE-specific artifacts from the main
  path.

### INIT-017 paused work

Wrong-shaped branch and commit reference:

- Branch: `feat/init-017-crossplane`
- Current head observed: `027b3b6`
- Dirty pipeline artifacts observed:
  - modified `.pipeline/research.md`
  - modified `.pipeline/synthesis.md`
  - untracked `.pipeline/prior-decisions-audit.md`
- Proposal artifact is not accepted for the corrected plan.

Reusable:

- The prior-decisions audit is valuable evidence. Its row IDs are used
  throughout this re-plan.
- The two-tier concept remains valid (`AUD-09`, `AUD-10`), but the substrate is
  now self-managed k3s, not VKE.
- Crossplane remains the app-cluster provisioning control plane (`AUD-15`,
  `AUD-17`, `AUD-20`, `AUD-21`), but its provider surface changes.
- The provider-honesty principle survives: do not expose fields a composition
  cannot honor.
- RBAC, deletion policy, connection-secret contracts, and channel-to-claim
  mapping remain real gaps (`AUD-18`, `AUD-19`, `AUD-20`, `AUD-21`).

Wrong-shaped and replaced:

- Provider-vultr VKE cluster composition is no longer the target. Remote app
  clusters are k3s-on-Vultr-VMs, not VKE clusters.
- The local proof must not be a stubbed VKE provider path. The local channel is
  a real k3d deployment target.
- Crossplane must provision app-cluster claims against the corrected target
  model: local k3d/single-cluster semantics first, remote Vultr Cloud Compute
  VM plus cloud-init k3s clusters later.
- Any synthesis question that asks the user to decide technical API versions,
  naming, secret names, or validation style should be replaced by engineering
  decisions documented in the proposal.

Disposition:

- Pause remains correct. Do not resume this branch.
- Restart Crossplane as INIT-106 after INIT-101 through INIT-105 establish the
  k3s, Flux, Infisical, S3-compatible storage, DNS, and TLS substrate.

## 3. Component Selection Table

| Layer | Component | Local channel config | Remote channel config |
| --- | --- | --- | --- |
| Kubernetes distribution | k3s | k3d running k3s in Docker | k3s installed by cloud-init on Vultr Cloud Compute VMs |
| Cluster fleet | Crossplane | Crossplane runs in local k3d; local channel may treat the local control cluster as the only cluster until proposal proves multi-k3d need | Crossplane runs on the remote control cluster and provisions app clusters as Vultr VM plus k3s claims |
| GitOps | Flux | Reconciles the local channel overlay from this repo | Same Flux resources reconcile remote channel overlays from this repo |
| Bootstrap secrets | SOPS+age | Per-channel age recipient only for bootstrap material | Same, per-channel recipient for bootstrap material |
| Runtime secrets | Infisical | Infisical instance plus Operator in local cluster | Infisical instance plus Operator in remote cluster |
| Object storage | S3-compatible API | MinIO in local cluster, channel endpoint points at MinIO service | Vultr Object Storage, channel endpoint points at Vultr S3-compatible URL |
| TLS | cert-manager | step-ca local CA Issuer | ACME Let's Encrypt ClusterIssuer |
| DNS | DNS controller shape | CoreDNS rewrites or local zone controller | ExternalDNS with Cloudflare provider |
| Ingress | Kong | Kong controller in local cluster | Kong controller in remote app cluster |
| Database | CloudNativePG | In-cluster Postgres instance | In-cluster Postgres instance |
| Auth | Authentik | Local Authentik instance | Remote Authentik instance |
| Authz | OPAL/Cedar | Local OPAL/Cedar stack | Same OPAL/Cedar stack |
| Access proxy | Pomerium | Local Pomerium routes for local hostnames | Remote Pomerium routes for remote domains |
| CI/CD | Buildkite | Agent in local container or local k3d worker path | Agent on Vultr VM or remote k3s worker path |
| Observability | kube-prometheus-stack plus OpenTelemetry Collector plus Loki | Prometheus, Grafana, Alertmanager, OTel Collector, Loki with local resource sizing | Same stack with remote sizing and retention |

### Known asymmetries

These are accepted provider/endpoint differences, not architecture
exceptions:

- DNS: local CoreDNS/local zone versus Cloudflare/ExternalDNS. Same hostnames
  and resource shapes; different provider.
- TLS issuer: local step-ca CA versus Let's Encrypt ACME. Same cert-manager
  Certificate/Issuer contract; different issuer backend.
- Object storage endpoint: local MinIO versus Vultr Object Storage. Same S3 API
  client path; different endpoint and credentials.
- Buildkite agent placement: local container versus remote VM/container. Same
  pipeline YAML and queue semantics; different execution host.

Anything beyond those differences should be treated as a design smell in the
per-INIT proposal phase.

### Observability pick

The corrected Phase 5 should ratify:

- `kube-prometheus-stack` for Prometheus, Grafana, and Alertmanager.
- OpenTelemetry Collector for OTLP ingestion, trace/log/metric collection, and
  context propagation.
- Loki for local-runnable structured log storage.

Why this pick:

- It addresses the audit's legacy observability rows without importing the
  full VictoriaMetrics, Elastic APM, Kafka, and StackStorm estate
  (`AUD-52`, `AUD-53`, `AUD-54`, `AUD-55`, `AUD-56`, `AUD-57`).
- It runs locally and remotely with the same controllers and manifests.
- It preserves Prometheus/Grafana/Alertmanager, which the legacy materials
  repeatedly named, while adding the missing OTLP and logging pieces.
- It does not reintroduce Kafka alert buses, vmalert-to-Kafka, or StackStorm
  automation into the Phase 5 minimum path.

This is a re-plan recommendation, not an INIT-117 proposal. INIT-117 still
must run the normal proposal and risk gate.

## 4. Channel Schema Extension

The current channel schema carries platform-substrate config such as region,
Kubernetes version, node pools, and state. The corrected schema must carry
provider and endpoint configuration for every environment-agnostic component.
This section sketches fields; it does not finalize the schema.

### Top-level fields to preserve

```yaml
schema_version: 2
id: local
parent: null
exposure: dev
tenant: null
allow_ephemeral_children: true
enabled_platforms:
  - kubernetes
```

These fields come from `channel-template-pattern.md` and remain the identity
contract for all channels.

### Kubernetes target

```yaml
kubernetes:
  distribution: k3s
  target: local # local | remote
  local:
    engine: k3d
    cluster_name: humility-local
    server_count: 1
    agent_count: 2
    ports:
      http: 8080
      https: 8443
  remote:
    provider: vultr
    region: ewr
    control_plane:
      count: 3
      plan: vc2-2c-4gb
    workers:
      - name: default
        count: 2
        plan: vc2-2c-4gb
    cloud_init_profile: k3s-server
```

For local channels, `remote` is absent. For remote channels, `local` is absent.
The field changes provider inputs, not the Kubernetes distribution.

### Cluster fleet

```yaml
fleet:
  control_cluster: true
  app_cluster_mode: in_cluster # in_cluster | crossplane_claim
  crossplane:
    provider: vultr-vm-k3s
    deletion_policy: Orphan
    connection_secret_namespace: crossplane-system
```

The proposal phase must decide exact CRD names and claim placement. The
important correction is that the provider target is not VKE.

### GitOps

```yaml
gitops:
  reconciler: flux
  source_repo: server-manager
  channel_path: ./gitops/channels/local
  branch: main
```

Local and remote use the same layout. The source URL can differ by channel
only as an endpoint setting.

### Bootstrap secrets

```yaml
bootstrap_secrets:
  provider: sops-age
  age_recipient_ref: local-age-recipient
  scope: bootstrap-only
```

This field must not imply runtime secret ownership.

### Runtime secrets

```yaml
runtime_secrets:
  provider: infisical
  endpoint: https://infisical.local.guildies.test
  operator_namespace: infisical-system
  project_slug: humility-local
  auth:
    kubernetes_auth_ref: infisical-k8s-auth
```

The channel carries endpoint and project references. The actual credentials are
bootstrap material or Infisical-managed values, never plaintext channel data.

### Object storage

```yaml
object_storage:
  api: s3
  endpoint: http://minio.minio-system.svc.cluster.local:9000
  region: local
  bucket_prefix: humility-local
  credentials_ref:
    provider: infisical
    secret_path: /platform/object-storage
```

Remote channels use Vultr Object Storage endpoint and region values. SDK code
must see only an S3-compatible endpoint.

### DNS

```yaml
dns:
  provider: coredns # coredns | cloudflare
  zone: local.guildies.test
  external_dns:
    enabled: false
    provider_config_ref: null
```

Remote channels set `provider: cloudflare` and enable ExternalDNS with a
Cloudflare provider credential reference.

### TLS

```yaml
tls:
  issuer_type: step-ca-local # step-ca-local | acme-letsencrypt
  issuer_ref: local-step-ca
  public_trust: false
```

Remote channels use ACME/Let's Encrypt and public trust. The cert-manager
resource shape remains the same.

### Ingress and auth

```yaml
ingress:
  controller: kong
  class_name: kong
  base_domain: local.guildies.test

auth:
  identity_provider: authentik
  access_proxy: pomerium
  authorization: opal-cedar
  identity_context_header: x-user-id
  channel_context_header: x-channel-id
```

These choices are not optional per channel. Channel config provides domains,
issuer refs, and resource sizing.

### Database

```yaml
database:
  operator: cloudnativepg
  cluster_name: humility-postgres
  instances: 1
  storage_size: 20Gi
  backup:
    endpoint_ref: object_storage
    bucket: humility-local-postgres-backups
```

Local and remote both use CloudNativePG. Size and retention differ.

### CI/CD

```yaml
cicd:
  provider: buildkite
  queue: local
  agent_target: local-container # local-container | vultr-vm-container
  registry:
    provider: ghcr
    repository_prefix: ghcr.io/oulipoly/server-manager
```

This sketch recommends GHCR for the Phase 5 registry decision because it is
simple, local-runnable as a pull target, does not add another Vultr-specific
surface, and avoids self-hosting Harbor/JFrog. INIT-108 must still ratify this
through the proposal/risk process.

### Discord identity

```yaml
discord:
  guild_class: beta # beta | live
  guild_id_ref:
    provider: infisical
    secret_path: /discord/guild-id
  bot_token_ref:
    provider: infisical
    secret_path: /discord/bot-token
```

Local channel targets the beta guild. Remote production-class channel targets
Humility. The bot is already registered in both contexts per
`discord-registration.md`.

## 5. New Phase 5 INIT List

### INIT-100: Phase 5 Reset

Scope: delete the wrong-shaped INIT-008, INIT-009, and paused INIT-017 work
from the main path while preserving their branches as references. Re-establish
the Phase 5 canon: environment-agnostic stack, local-as-first-deployment,
self-managed k3s everywhere, SOPS bootstrap-only, Infisical runtime secrets,
channels as provider/endpoint parameterization, and no VKE. This initiative
also drafts the D8 decision entry and marks D7 VKE/local-only language as
superseded. Addresses `AUD-03`, `AUD-08`, `AUD-22`, `AUD-37`, `AUD-38`,
`AUD-59`, `AUD-62`, `AUD-63`, `AUD-64`, `AUD-67`; respects
`environment-agnostic-stack.md`, `channel-template-pattern.md`, and
`no-backwards-compatibility.md`.

Dependencies: none.

Local channel as first deployment target: no cluster deployment yet; this is
the reset gate that authorizes local as the first target for every later INIT.

Magnitude: S.

Anti-scope: no implementation of k3s, Flux, Infisical, Crossplane, or app
workloads; no merge of VKE/kind artifacts.

### INIT-101: Self-Managed k3s Control Cluster

Scope: replace INIT-008. Define and implement the control-cluster substrate as
self-managed k3s everywhere. The local channel creates k3d; remote channels use
OpenTofu to provision Vultr Cloud Compute VMs and cloud-init to install k3s.
Keep Vultr VPC, firewall, object-storage state backend, and channel-template
ideas where they still apply. Produce a real local k3d control cluster as the
done state. Addresses `AUD-01`, `AUD-02`, `AUD-03`, `AUD-04`, `AUD-05`,
`AUD-06`, `AUD-09`, `AUD-10`, `AUD-22`, `AUD-59`, `AUD-67`; respects
`environment-agnostic-stack.md` and `two-tier-cluster-architecture.md`.

Dependencies: INIT-100.

Local channel as first deployment target: yes, k3d cluster is created and
usable.

Magnitude: XL.

Anti-scope: no VKE module, no VKE root, no app clusters, no Flux install, no
runtime secrets, no public DNS.

### INIT-102: GitOps Substrate

Scope: replace INIT-009. Install Flux into the local k3d control cluster,
reconcile this repo's channel overlay, keep Kustomize/channel layout, and keep
SOPS+age only for bootstrap secrets. Use the corrected channel schema extension
and k3d target. The done state is Flux actively reconciling the local channel.
Addresses `AUD-11`, `AUD-12`, `AUD-13`, `AUD-14`, `AUD-60`, `AUD-61`,
`AUD-62`; respects `channel-template-pattern.md` and
`environment-agnostic-stack.md`.

Dependencies: INIT-101.

Local channel as first deployment target: yes, Flux reconciles local k3d.

Magnitude: L.

Anti-scope: no runtime secret ownership, no app workload deployment, no
Crossplane claims, no kind-only harness, no compatibility `k8s/` path.

### INIT-103: Infisical Runtime Secret Store

Scope: add Infisical as the runtime secret manager. Deploy Infisical and the
Infisical Operator locally, define `InfisicalSecret` CRD usage, namespaces,
RBAC, bootstrap credential handoff from SOPS+age, and secret ownership for
Crossplane, app workloads, CloudNativePG, Authentik, Pomerium, Buildkite, S3,
and Discord tokens. Addresses `AUD-37`, `AUD-38`, `AUD-39`, `AUD-62`,
`AUD-69`; respects `environment-agnostic-stack.md`,
`secrets-and-domains.md`, and deleted-history evidence from `5781727` and
`be89f7b`.

Dependencies: INIT-102.

Local channel as first deployment target: yes, local Infisical syncs at least
one real Kubernetes Secret from a local project.

Magnitude: L.

Anti-scope: no real Cloudflare password/API token in git, no SOPS runtime
secrets, no SealedSecrets, no app-specific secret schema beyond required
ownership contracts.

### INIT-104: S3-Compatible Storage Layer

Scope: deploy MinIO in the local channel and define the S3-compatible contract
that remote channels satisfy with Vultr Object Storage. Define bucket naming,
endpoint injection, credentials via Infisical, lifecycle/versioning posture,
and application SDK configuration. Addresses `AUD-05`, `AUD-30`, `AUD-48`,
`AUD-49`, `AUD-50`; respects `environment-agnostic-stack.md` and
`plans/research/self-hosted-s3.md`.

Dependencies: INIT-103.

Local channel as first deployment target: yes, local MinIO is reachable and a
test bucket/object round trip succeeds.

Magnitude: M.

Anti-scope: no MinIO claim bus, no bucket-watched Flux, no SeaweedFS fallback
implementation, no provider-native-only application path.

### INIT-105: TLS, DNS, and Certificate Automation

Scope: deploy cert-manager, local step-ca issuer, local DNS/CoreDNS rewriting,
and the remote-channel ExternalDNS/Cloudflare plus ACME/Let's Encrypt contract.
Define hostname conventions without committing credentials. Local done state is
valid local TLS for local channel hostnames. Addresses `AUD-23`, `AUD-24`,
`AUD-36`, `AUD-40`; respects `environment-agnostic-stack.md`,
`secrets-and-domains.md`, and `plans/research/pomerium-smallstep.md`.

Dependencies: INIT-102, INIT-103.

Local channel as first deployment target: yes, local cert-manager issues certs
through step-ca for local hostnames.

Magnitude: L.

Anti-scope: no public Cloudflare mutation, no WAF/origin-shield policy beyond
explicit deferral, no production domain cutover, no visible Discord action.

### INIT-106: Application Cluster Provisioning with Crossplane

Scope: replace paused INIT-017. Install Crossplane in the control cluster and
define app-cluster claims/compositions targeting self-managed k3s clusters, not
VKE. Local channel behavior must be real and environment-agnostic: either the
local control cluster is explicitly the only local app target or a clean
multi-k3d app-cluster path is proposed and deployed. Remote app clusters are
Vultr VMs plus cloud-init k3s. Define RBAC, deletion policy, connection-secret
contracts, and channel-to-claim mapping. Addresses `AUD-15`, `AUD-16`,
`AUD-17`, `AUD-18`, `AUD-19`, `AUD-20`, `AUD-21`, `AUD-22`, `AUD-26`,
`AUD-63`; respects `two-tier-cluster-architecture.md`,
`environment-agnostic-stack.md`, and `channel-template-pattern.md`.

Dependencies: INIT-101, INIT-102, INIT-103.

Local channel as first deployment target: yes, Crossplane runs locally and the
local app target is reconciled according to the accepted proposal.

Magnitude: XL.

Anti-scope: no provider-vultr VKE composition, no stub-only provider, no app
workloads, no network-policy baseline, no remote cluster creation in Phase 5.

### INIT-107: Cluster Security Baseline

Scope: apply default Kubernetes security posture on every cluster: namespaces,
RBAC boundaries, Pod Security Standards, NetworkPolicies, service-account
rules, secret access boundaries, image-pull policy, and controller permissions.
Local done state is the baseline enforced in k3d. Addresses `AUD-18`,
`AUD-25`, `AUD-26`, `AUD-41`, `AUD-57`, `AUD-66`; respects
`two-tier-cluster-architecture.md` and `environment-agnostic-stack.md`.

Dependencies: INIT-102, INIT-106 for app-cluster policy surfaces where needed.

Local channel as first deployment target: yes, policies are enforced in local
k3d and tested against allowed/denied fixtures.

Magnitude: L.

Anti-scope: no service mesh unless INIT-115 later ratifies it, no Falco/Trivy
runtime stack unless split into a later security-hardening initiative, no
provider-specific CNI assumptions.

### INIT-108: Container Delivery and Image Registry

Scope: add Dockerfiles/build definitions for `services/api` and
`services/discord`, choose the production image registry, define channel-aware
tags, local image loading into k3d, and remote pull contracts. Recommendation:
GHCR first, not Vultr Container Registry and not self-hosted Harbor/JFrog,
unless proposal research finds a blocker. Addresses `AUD-42`, `AUD-43`,
`AUD-46`, `AUD-47`, `AUD-51`; respects `platform-stack.md` Buildkite decision
and `plans/research/buildkite-capabilities.md`.

Dependencies: INIT-101, INIT-102.

Local channel as first deployment target: yes, images build and run from local
registry/k3d load path.

Magnitude: L.

Anti-scope: no remote push unless explicitly approved in a later deployment
phase, no Harbor/JFrog, no mutable `latest` as the deployment contract, no
Buildkite pipeline yet.

### INIT-109: CI/CD via Buildkite

Scope: implement Buildkite pipeline YAML, local Buildkite agent execution, test
and build steps, channel-aware promotion metadata, and remote-agent placement
contract. Buildkite observes and prepares; Flux reconciles. Addresses `AUD-42`,
`AUD-43`, `AUD-44`, `AUD-45`, `AUD-46`; respects
`plans/research/buildkite-capabilities.md` and `platform-stack.md`.

Dependencies: INIT-108, INIT-102.

Local channel as first deployment target: yes, local agent runs the same
pipeline against the local channel.

Magnitude: L.

Anti-scope: no Dagger/GitLab as canonical CI, no Kafka/Debezium/Redis
deployment bus, no CI-driven direct cluster mutation, no production release.

### INIT-110: Ingress with Kong

Scope: deploy Kong as the north-south ingress controller in the local channel,
wire local hostnames/TLS from INIT-105, define route conventions, and prepare
the remote-channel equivalent. Addresses `AUD-27`, `AUD-33`, `AUD-35`,
`AUD-39`, `AUD-65`; respects `environment-agnostic-stack.md` and legacy
Kong/auth evidence from `5781727`.

Dependencies: INIT-105, INIT-107.

Local channel as first deployment target: yes, local Kong routes a test
service over local TLS.

Magnitude: M.

Anti-scope: no public route exposure, no auth bypass for production, no app
workload rollout beyond test service, no alternative ingress controller unless
proposal risk rejects Kong.

### INIT-111: Data Plane with CloudNativePG and Atlas

Scope: deploy CloudNativePG locally, define Postgres clusters for app runtime,
wire Atlas SQL-first migrations, migration job ordering, pg_stat_statements,
and app database credential delivery via Infisical. Local done state runs real
migrations against local CloudNativePG. Addresses `AUD-28`, `AUD-29`,
`AUD-30`, `AUD-64`; respects `plans/research/database-stack.md` and
`environment-agnostic-stack.md`.

Dependencies: INIT-103, INIT-104, INIT-107.

Local channel as first deployment target: yes, local CloudNativePG and Atlas
migration proof run in cluster.

Magnitude: L.

Anti-scope: no "migrations on deploy" wording without an actual local deploy
contract, no managed Postgres exception for local, no ORM-first migration
stack, no production data migration.

### INIT-112: Backup and DR

Scope: implement CloudNativePG backups to the S3-compatible object layer,
define RPO/RTO, restore drill, state/object/db boundaries, and deletion safety.
Local done state backs up to MinIO and restores into a local database cluster.
Remote channels use Vultr Object Storage. Addresses `AUD-30`, `AUD-48`,
`AUD-49`, `AUD-70`; respects `plans/research/self-hosted-s3.md` and
`environment-agnostic-stack.md`.

Dependencies: INIT-104, INIT-111.

Local channel as first deployment target: yes, backup and restore drill pass
locally.

Magnitude: L.

Anti-scope: no Velero unless proposal selects it for cluster-resource backup,
no remote restore drill in Phase 5, no backup-only-without-restore acceptance.

### INIT-113: Application Workloads

Scope: deploy `services/api` and `services/discord` to the local channel using
the same manifests intended for remote channels. Local bot connects to the beta
guild; remote production-class bot connects to Humility. Wire images, runtime
config, Infisical secrets, database, ingress, health checks, and startup order.
Addresses `AUD-31`, `AUD-32`, `AUD-64`, `AUD-65`; respects
`discord-registration.md`, `environment-agnostic-stack.md`, and the three-tier
live-server safety rule.

Dependencies: INIT-108, INIT-110, INIT-111, INIT-103.

Local channel as first deployment target: yes, API and Discord daemon run in
local k3d and target beta guild only.

Magnitude: XL.

Anti-scope: no live Humility mutation, no production token use in local, no
registration work, no public production exposure.

### INIT-114: Auth Stack

Scope: deploy Authentik, OPAL/Cedar, and Pomerium locally; define identity
claims, Pomerium route integration, Kong identity propagation, OPAL data sync,
and app-side authorization contract. Local done state gates local admin routes
and runs at least one policy decision path. Addresses `AUD-33`, `AUD-34`,
`AUD-35`, `AUD-39`, `AUD-40`, `AUD-41`, `AUD-65`; respects
`plans/platform-decisions-overlay.md`, `plans/research/pomerium-smallstep.md`,
and deleted-history auth evidence.

Dependencies: INIT-103, INIT-110, INIT-113.

Local channel as first deployment target: yes, local auth stack protects local
routes.

Magnitude: XL.

Anti-scope: no Casbin re-litigation, no external workforce SSO requirement for
local proof, no service mesh by default, no production user onboarding.

### INIT-115: Access Policy, Break-glass, and Service Identity

Scope: operationalize access-policy-as-code, Pomerium policy management,
break-glass process, service identity, and the Smallstep scope decision. Local
done state includes local policy reconciliation, emergency-access runbook, and
explicit service-mesh/no-service-mesh decision. Addresses `AUD-36`, `AUD-39`,
`AUD-40`, `AUD-41`, `AUD-66`, `AUD-69`; respects
`plans/research/pomerium-smallstep.md` and `memory/feedback-escalation-bar.md`.

Dependencies: INIT-114, INIT-107.

Local channel as first deployment target: yes, local policy-as-code and access
tests run.

Magnitude: M/L.

Anti-scope: no Cloudflare Access duplication, no Linkerd import unless
proposal ratifies it, no provider-side break-glass account creation in Phase 5.

### INIT-116: Tenant and Channel Isolation Model

Scope: operationalize the `tenant` field and channel isolation: namespace,
cluster, database, object-storage prefix/bucket, network policy, Discord guild
identity, and auth realm boundaries. Local done state creates at least one
ephemeral or child local channel fixture that exercises isolation without
touching live Discord. Addresses `AUD-06`, `AUD-07`, `AUD-21`, `AUD-32`,
`AUD-68`; respects `channel-template-pattern.md`,
`environment-agnostic-stack.md`, and `discord-registration.md`.

Dependencies: INIT-106, INIT-111, INIT-113, INIT-114.

Local channel as first deployment target: yes, isolation is tested locally.

Magnitude: L.

Anti-scope: no customer/internal live channel activation, no production
multi-tenant rollout, no hard dev/staging/prod roots.

### INIT-117: Observability

Scope: deploy the observability baseline: kube-prometheus-stack,
OpenTelemetry Collector, Loki, dashboards, alert routes, structured logging
contract, metrics endpoint hardening, and trace/context propagation. Local done
state observes the local stack and application workloads. Addresses `AUD-52`,
`AUD-53`, `AUD-54`, `AUD-55`, `AUD-56`, `AUD-57`; respects
`environment-agnostic-stack.md` and deleted-history observability evidence.

Dependencies: INIT-107, INIT-113, INIT-114 for identity context fields where
needed.

Local channel as first deployment target: yes, local metrics/logs/traces and
alerts work.

Magnitude: L.

Anti-scope: no Kafka alert bus, no StackStorm, no Elastic/VictoriaMetrics
estate unless proposal risk rejects the recommended stack, no dashboards-only
without alerting/logging/tracing.

## 6. Explicit Supersession Decisions

Draft `DECISIONS.md` entry:

```markdown
## D8 - 2026-04-26 - Environment-agnostic Phase 5 reset: local-as-first-deployment and self-managed k3s everywhere

**Context**: Phase 5 was originally planned from a shallow read of platform
proposals. INIT-008 shipped a VKE-shaped substrate, INIT-009 shipped
kind/local-verification-shaped GitOps, and INIT-017 began VKE-focused
Crossplane work. The prior-decisions audit found 70 decisions with 12 missing,
5 contradicted, and 8 superseded. The governing correction is now recorded in
`environment-agnostic-stack.md`: local is a deployment target, not a simulation;
same components run locally and remotely; channels carry provider and endpoint
config.

**Decision**:
1. Phase 5 is reset around an environment-agnostic stack. The local channel is
   the first deployment target.
2. Kubernetes is self-managed k3s everywhere: k3d locally and k3s on Vultr
   Cloud Compute VMs remotely. VKE is no longer the workload/runtime substrate.
3. OpenTofu provisions Vultr cloud primitives and remote VMs; cloud-init
   bootstraps k3s on those VMs.
4. Crossplane remains the app-cluster fleet control plane, but it provisions
   k3s-on-VM app clusters, not VKE clusters.
5. Flux remains the GitOps reconciler.
6. SOPS+age remains bootstrap-only. Infisical is the runtime secret store.
7. Channel templates remain the environment model. Per-channel config carries
   target type, object-storage endpoint, DNS provider, TLS issuer, Infisical
   endpoint, Buildkite queue/agent target, Discord guild class, and resource
   sizing.
8. Every Phase 5 initiative must deploy a real component into the local
   channel as its done state. Render-only, stub-provider, dry-run-only, and
   local-exception designs are not accepted.
9. Wrong-shaped INIT-008, INIT-009, and paused INIT-017 work are preserved as
   reference branches only and are not merged into the main path.

**Supersedes**:
1. Hetzner / kube-hetzner / k3s-via-kube-hetzner as specific tooling. k3s
   remains; Hetzner and kube-hetzner do not. Superseded by D8 self-managed k3s
   on Vultr VMs.
2. VKE managed Kubernetes as the workload/runtime substrate. Superseded by D8
   k3s on k3d/Vultr VMs.
3. The prior VKE-specific cluster target. Vultr and OpenTofu survive; VKE does not.
4. The old `local-only verification` framing. Superseded by local-as-first
   deployment in `environment-agnostic-stack.md` and D8.
5. kind as the local Kubernetes target for Phase 5. Superseded by k3d because
   k3d runs k3s.
6. SOPS+age as a runtime secret store. Superseded by SOPS+age bootstrap-only
   plus Infisical runtime secrets.
7. SealedSecrets. Superseded by SOPS+age bootstrap-only plus Infisical runtime
   secrets.
8. Dagger and GitLab CI as canonical CI/CD. Superseded by Buildkite.
9. Kafka, Debezium, and Redis as the deployment/CI bus. Deferred indefinitely;
   Buildkite plus Flux is the deployment path.
10. JFrog and Harbor as Phase 5 image-registry/platform requirements.
    Superseded by a simpler registry decision to be ratified in INIT-108,
    with GHCR as the recommended default.
11. MinIO claim buses and bucket-watched Flux. Superseded by Git-backed Flux;
    MinIO survives only as local S3-compatible object storage.
12. Fixed `infra/environments/{dev,staging,production}/` roots. Superseded by
    channel templates.
13. Separate hard `dev`, `staging`, and `production` environments. Superseded
    by channels with exposure, parent, tenant, and endpoint/provider config.
14. Provider-native-only object storage as an app-facing abstraction.
    Superseded by an S3-compatible layer: MinIO local, Vultr Object Storage
    remote.
15. VKE/provider-vultr Crossplane app-cluster compositions. Superseded by
    k3s-on-Vultr-VM compositions and local k3d-compatible local-channel
    behavior.
16. Linkerd/service mesh as an inherited Phase 5 default. Superseded by an
    explicit INIT-115 decision: no service mesh unless the proposal/risk gate
    accepts it.
17. VictoriaMetrics/Elastic/Kafka/StackStorm observability/AIOps as the Phase
    5 default. Superseded by INIT-117's recommended Prometheus/Grafana/
    Alertmanager/OpenTelemetry/Loki stack unless its proposal changes that
    through the normal gate.
18. Cloudflare edge/WAF/origin shielding as part of the minimum DNS/TLS
    initiative. INIT-105 owns DNS automation; Cloudflare edge security is
    deferred unless separately scheduled.

**Consequences**:
- INIT-100 through INIT-117 replace the old INIT-008 through INIT-017 main
  path.
- No VKE module, VKE channel schema, kind-only harness, SOPS-runtime framing,
  or VKE Crossplane work should be merged.
- Future per-INIT proposals cite D8 and `environment-agnostic-stack.md` as
  controlling sources.
- Any initiative that cannot deploy a real local-channel component must stop
  in proposal/risk and choose a different component.
```

Supersession count in the draft: 18.

## 7. Risks of This Re-plan

### Sunk cost

Accepting this re-plan writes off shipped work:

- INIT-008 branch `feat/init-008-platform-bootstrap` at `9f7090f`.
- INIT-009 branch `feat/init-009-gitops-substrate` at `027b3b6`.
- Paused INIT-017 branch `feat/init-017-crossplane` at `027b3b6` plus dirty
  pipeline artifacts.

Some ideas survive, but the main-path implementation must be redone because
the substrate changed from VKE/kind/local-verification to
k3s/k3d/local-deployment.

### Time to re-implement

The old 9-INIT plan becomes an 18-INIT plan. The count rises because the
previous plan hid runtime secrets, S3 local parity, TLS/DNS parity, registry
choice, tenant isolation, access policy, and observability decisions inside
underspecified downstream work.

### New operational burden

Self-managed k3s on Vultr VMs creates more day-2 ownership than VKE. The
reason to accept that burden is environmental parity: VKE cannot be the same
distribution locally and remotely. INIT-101 must handle upgrades, cloud-init,
node bootstrap, control-plane shape, and remote operations honestly.

### Crossplane complexity changes shape

VKE app-cluster claims are replaced by VM plus cloud-init k3s claims. This may
require more composition work than the provider-vultr VKE resource. The
proposal phase must keep the claim surface small and provider-honest.

### Local channel may reveal more dependencies

Because local is now real, every component must actually work in k3d. This may
surface resource limits, DNS/TLS friction, Authentik/Infisical bootstrapping
order, or CI agent networking issues earlier than the old render-only plan.
That is the point, but it costs time.

### This re-plan can still miss gaps

The audit proved that prior shallow reads missed substantial architecture. This
artifact reduces that risk by citing the audit and memory files, but it is not
magic. Per-INIT research and proposal gates still need to re-check component
details, provider capabilities, and integration ordering.

### Value-level risk

The user loses the simplicity and managed-service comfort of VKE. The user
gains environment parity and a real local deployment path. That tradeoff is
architectural, not just technical, because it changes ownership burden.

## 8. What I Want From the User Before Resuming Per-INIT Pipeline

1. Confirm the sunk-cost write-off: INIT-008 and INIT-009 shipped work, plus
   paused INIT-017 pipeline artifacts, are reference-only and not merged into
   the corrected main path.
2. Confirm the 18-initiative ordering and dependency shape: INIT-100 through
   INIT-117 replace the 9-INIT Phase 5 plan.
3. Confirm the D8 supersession list, especially VKE removal, local-as-first
   deployment, Infisical runtime secrets, and SOPS bootstrap-only.

These are value-level because they decide what work is discarded and what
strategic burden the platform accepts. I am not escalating implementation
details such as exact CRD names, namespace names, chart versions, or schema
field spelling.

## Appendix A: Audit Row Crosswalk

| Audit row | Re-plan handling |
| --- | --- |
| `AUD-01` | Vultr remains the remote hosting provider. |
| `AUD-02` | OpenTofu remains the remote cloud IaC layer. |
| `AUD-03` | VKE control cluster superseded by k3s control cluster. |
| `AUD-04` | Shared Vultr network baseline remains for remote channels. |
| `AUD-05` | Object-storage remote state remains; app object layer becomes S3-compatible local/remote. |
| `AUD-06` | Channel templates remain controlling. |
| `AUD-07` | Old `dev` active-channel framing replaced by `local` first target; non-local channels deferred. |
| `AUD-08` | Local-only verification superseded by local-as-first deployment. |
| `AUD-09` | Two-tier architecture retained. |
| `AUD-10` | Control cluster does not host remote app workloads; local channel behavior must be explicit. |
| `AUD-11` | Flux retained. |
| `AUD-12` | This repo remains GitOps source. |
| `AUD-13` | SOPS+age retained as bootstrap-only. |
| `AUD-14` | Old roots/compatibility paths remain deleted. |
| `AUD-15` | Crossplane retained, target corrected. |
| `AUD-16` | Provider-vultr VKE maturity no longer controls; new provider/composition surface required. |
| `AUD-17` | Claim surface must stay small and provider-honest. |
| `AUD-18` | RBAC assigned to INIT-106/107. |
| `AUD-19` | Deletion safety assigned to INIT-106/112. |
| `AUD-20` | Connection contract assigned to INIT-106. |
| `AUD-21` | Channel-to-claim mapping assigned to INIT-106 and INIT-116. |
| `AUD-22` | VKE machine-config contradiction resolved by self-managed k3s. |
| `AUD-23` | cert-manager/ExternalDNS retained with local step-ca/CoreDNS equivalents. |
| `AUD-24` | Cloudflare DNS retained; edge/WAF deferred. |
| `AUD-25` | Cluster security baseline assigned to INIT-107. |
| `AUD-26` | Provider CNI ambiguity replaced by k3s policy baseline. |
| `AUD-27` | Kong retained. |
| `AUD-28` | CloudNativePG and Atlas retained. |
| `AUD-29` | SQL-first conventions retained. |
| `AUD-30` | Backup/DR assigned to INIT-112. |
| `AUD-31` | API and Discord workloads assigned to INIT-113. |
| `AUD-32` | Discord beta/live isolation assigned to INIT-113/116. |
| `AUD-33` | Authentik retained. |
| `AUD-34` | OPAL/Cedar retained. |
| `AUD-35` | Pomerium retained. |
| `AUD-36` | step-ca conditional as PKI, but mandatory local TLS issuer for cert-manager. |
| `AUD-37` | Infisical added as INIT-103. |
| `AUD-38` | InfisicalSecret/Operator added as INIT-103. |
| `AUD-39` | Access split assigned to INIT-114/115. |
| `AUD-40` | Policy-as-code assigned to INIT-115. |
| `AUD-41` | Service identity assigned to INIT-115. |
| `AUD-42` | Buildkite retained. |
| `AUD-43` | Local and remote agent placement assigned to INIT-109. |
| `AUD-44` | GitLab/Dagger superseded. |
| `AUD-45` | Kafka/Debezium/Redis deployment bus deferred indefinitely. |
| `AUD-46` | Registry decision assigned to INIT-108, GHCR recommended. |
| `AUD-47` | Harbor/JFrog superseded for Phase 5. |
| `AUD-48` | Provider object storage retained for remote; MinIO added locally. |
| `AUD-49` | MinIO chosen for local S3-compatible parity. |
| `AUD-50` | MinIO claim bus/bucket-watched Flux superseded. |
| `AUD-51` | Local image path retained; remote registry contract added. |
| `AUD-52` | Observability implementation assigned to INIT-117. |
| `AUD-53` | Prometheus/Grafana/Alertmanager accepted. |
| `AUD-54` | OpenTelemetry/OTLP accepted. |
| `AUD-55` | Loki/structured logging added. |
| `AUD-56` | Alert routing via Alertmanager, no Kafka bus. |
| `AUD-57` | Metrics hardening assigned to INIT-107/117. |
| `AUD-58` | SealedSecrets superseded. |
| `AUD-59` | Hetzner/kube-hetzner tooling superseded; k3s itself restored. |
| `AUD-60` | Local simulation superseded by local deployment. |
| `AUD-61` | Fixed env roots superseded by channels. |
| `AUD-62` | SOPS runtime contradiction resolved by Infisical. |
| `AUD-63` | Stubbed Crossplane local smoke replaced by real local deployment semantics. |
| `AUD-64` | Migration wording corrected to real local deploy/migration proof. |
| `AUD-65` | Auth/public exposure order handled by local deployment and INIT-114/115 gates. |
| `AUD-66` | Service mesh explicitly not inherited; INIT-115 decides. |
| `AUD-67` | Container runtime follows k3s/containerd unless proposal proves otherwise. |
| `AUD-68` | Tenant isolation assigned to INIT-116. |
| `AUD-69` | Break-glass assigned to INIT-115. |
| `AUD-70` | Deployment boundary replaced by channel-onboarding after local Phase 5, not a separate "real deployment" re-architecture. |

## Appendix B: Deleted-History Ratifications and Supersessions

Ratified from deleted history:

- Infisical runtime secret architecture from `5781727` and `be89f7b`.
- Authentik, OPAL/Cedar, Pomerium, and Kong roles from `5781727`.
- Structured observability context and OTLP concepts from `5781727` and
  `4e2a70c`.
- Buildkite/Flux replacement of Dagger/GitLab/custom CI from current overlay
  and `775ef4c`.
- Provider-native remote object storage plus S3-compatible abstraction from
  current research and legacy MinIO/Vultr split.

Superseded from deleted history:

- Hetzner/kube-hetzner as tooling.
- VKE managed Kubernetes.
- Dagger, GitLab Runner, and self-hosted Harbor/JFrog as required Phase 5
  platform surfaces.
- Kafka/Debezium/Redis deployment orchestration.
- Bucket-watched Flux and MinIO claim buses.
- SealedSecrets.
- Linkerd as a default.
- VictoriaMetrics/Elastic/Kafka/StackStorm as the default observability/AIOps
  estate.
- Fixed environment roots and static dev/staging/production environment
  taxonomy.

## Appendix C: Recommended First Resume Point

After user review, resume with INIT-100, not INIT-101. The reset initiative
should land the D8 decision, replace the Phase 5 index, and mark the wrong
branches/artifacts as reference-only before any per-INIT proposal work starts.
