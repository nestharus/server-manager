# INIT-103 Synthesis

This synthesis binds INIT-103's design decisions before the proposal phase.
Each D-record names the decision, the research evidence supporting it, the
alternatives rejected, and the consequence for the proposal phase and
downstream INITs. Synthesis is grounded in research only; no decision below
introduces design specifics beyond what is needed to bind the choice.

Source: `worktrees/init-103-infisical-runtime-secrets/.pipeline/research.md`.
Section references below use that file unless otherwise noted. INIT-102's
binding contract is at
`worktrees/init-102-gitops-substrate/.pipeline/proposal.md` and its synthesis
D-records D1..D11 at
`worktrees/init-102-gitops-substrate/.pipeline/synthesis.md`.

## Decision Records

### D1 — D-INFISICAL-INSTALL

**Decision**: INIT-103 installs the Infisical server through **raw committed
manifests** under `gitops/channels/local/infisical-server/`, rendered at
implementation time from the upstream Infisical Helm chart
(`infisical-helm-charts/infisical-standalone`) via `helm template`. The
rendered output is reviewed, pinned, and committed; Flux's
`kustomize-controller` applies it through the existing local channel
`Kustomization/humility-local`. No `HelmRelease`, no `OCIRepository`, no
runtime Helm fetch.

**Evidence**: research §2.4, §8.3. INIT-102's reconciler shape (Flux
`source-controller` + `kustomize-controller` only, no `helm-controller`)
forces raw manifests at runtime (research §2.4; INIT-102 proposal §1, §7;
INIT-102 synthesis D2). Upstream Helm and Kustomize sources both exist
(research §2.4, §3.5); rendering Helm to raw manifests gives a reviewable
diff and preserves upstream defaults (resource requests, PVC sizes,
init/probe shapes per research §2.1, §2.3).

**Alternatives rejected**:
- `HelmRelease` via `helm-controller`: forbidden by INIT-102 D2 (controller
  excluded from vendored Flux components).
- `OCIRepository`-backed source: INIT-102 substrate exposes only
  `GitRepository` source — the in-cluster Git daemon (INIT-102 D4) is the
  only seeded source.
- Hand-author manifests from the env-var contract (research §2.2): more
  error-prone than rendering the upstream chart and loses upstream PVC,
  probe, and resource defaults (research §2.1, §2.3).

**Consequence**: Implementation needs `helm` available at render time
(currently missing per research §8.1). Rendered output is committed at a
pinned chart version. Upgrade is an explicit re-render + commit, not a
runtime fetch. Channel overlay layout extends INIT-102's
`gitops/channels/local/` per D8 below.

---

### D2 — D-OPERATOR-INSTALL

**Decision**: INIT-103 installs the Infisical Kubernetes Operator the same
way as the server: **raw committed manifests** under
`gitops/channels/local/infisical-operator/`, rendered at implementation time
from the upstream operator Helm chart
(`infisical-helm-charts/secrets-operator` v0.10.32). All six v0.10.32 CRDs
ship in the rendered set because CRDs are cluster-scoped and the chart owns
their installation; only `InfisicalSecret` is exercised by the INIT-103
proof (D9 below).

**Evidence**: research §3.5 (operator chart at v0.10.32; raw `config/`
Kustomize tree also exists), §8.3 (raw manifests through Flux without Helm
runtime), §3.2 (six CRDs in the v0.10.32 repo: `InfisicalSecret`,
`InfisicalPushSecret`, `InfisicalDynamicSecret`, `ClusterGenerator`,
`Password`, `UUID`). The operator chart's image-tag/appVersion mismatch
(chart v0.10.32 vs values manager image `v0.10.31`, research §3.5) is an
implementation-time verification item; the rendered manifest pins the actual
image used.

**Alternatives rejected**:
- `HelmRelease` via `helm-controller`: forbidden by INIT-102 D2.
- Direct apply of upstream `kubectl-install/install-secrets-operator.yaml`
  (research §2.4): a single opaque blob, harder to review, no version
  pinning of constituent images.
- Upstream `config/` Kustomize tree as the source of truth (research §2.4,
  §3.5): viable but produces less-canonical defaults than the chart and
  diverges from D1's chart-render shape; keeping a single render path keeps
  the implementation surface small.
- Subset of CRDs: CRDs are cluster-scoped and the chart installs them as a
  set; cherry-picking would require maintaining a divergent CRD selector
  with no proven benefit for the INIT-103 proof.

**Consequence**: SLICE-103.01 owns operator render and pin. The same
`helm template` workflow used in D1 covers both renders. The cluster-wide
CRD set is acceptable here because the operator's CR scope is namespaced
(research §3.4) and tenant isolation is INIT-116's concern.

---

### D3 — D-OPERATOR-AUTH

**Decision**: For INIT-103's first local proof, the Infisical Operator
authenticates to Infisical using **Universal Auth (UA)**. The
`InfisicalSecret` CR uses `authentication.universalAuth` with a
`credentialsRef` to a Kubernetes Secret containing `clientId` and
`clientSecret`. Project scope is bound by `secretsScope.projectId`,
`secretsScope.envSlug`, and `secretsScope.secretsPath`. Native Kubernetes
Auth and service-token auth are not used in INIT-103.

**Evidence**: research §4.2, §4.4, §3.3. UA carries explicit project scope
in the CRD (`projectId`, `envSlug`, `secretsPath`; research §3.3, §4.2),
returns short-lived access tokens with TTL (default 7200s, research §4.2),
and supports periodic-token renewal that mitigates static-credential risk
after the initial bootstrap (research §4.2). UA's required bootstrap input
(a single Kubernetes Secret with `clientId`/`clientSecret`) maps directly
to the channel schema fields enumerated in research §5.2. Service-token auth
is functionally simpler at the CRD level but leaves a fully static token
(research §4.1) and the sample CRD shape ties scope to the token's own
permissions rather than carrying explicit project IDs (research §4.1).
Native Kubernetes Auth requires Infisical to be pre-configured to trust the
specific cluster's service accounts (research §4.3), which adds first-run
configuration without reducing the chicken-and-egg burden (research §6.2).

**Alternatives rejected**:
- Service token: deprecated direction for new identities; static credential
  with no rotation; CRD scope tied to token, weaker fit for channel-driven
  project/env binding (research §3.3, §4.1).
- Native Kubernetes Auth: requires the Infisical instance to be
  pre-configured with allowed service accounts/namespaces and (when no
  central token reviewer JWT exists) `system:auth-delegator` on the
  Operator's SA (research §4.3); the same first-run admin/identity setup is
  still needed before the Operator can authenticate, with no offsetting
  simplification for INIT-103's local proof (research §4.4, §6.2, §6.3).
- Multiple auth methods on one CR: research §3.3 says only one method
  should be defined per `InfisicalSecret`.

**Consequence**: SLICE-103.04 (bootstrap) and SLICE-103.05 (sample
`InfisicalSecret`) consume the same UA credential delivery. Channel schema
fields for UA secret name/namespace and project/env/path are bound in D8.
INIT-104+ inherit the UA pattern (D10).

---

### D4 — D-SECRET-ZERO

**Decision**: Bootstrap is split into two distinct deliveries:

1. **Infisical server root secrets** (`ENCRYPTION_KEY`, `AUTH_SECRET`,
   `SITE_URL`, `DB_CONNECTION_URI`, `REDIS_URL`): committed as a
   SOPS-encrypted Secret at
   `gitops/bootstrap/infisical-server-bootstrap.enc.yaml`, decrypted by
   Flux during the bootstrap-tier reconcile, applied into namespace
   `infisical-system` as `Secret/infisical-server-bootstrap`, and consumed
   by the server Deployment via `envFrom`. This is bootstrap-tier because
   the server cannot start without these values (research §2.2, §6.2, §7.1)
   and SOPS already owns the bootstrap-tier delivery channel established by
   INIT-102 D5/D6.

2. **Operator UA credential** (`clientId`, `clientSecret`): generated
   **post-server-startup** by a one-shot bootstrap script
   (`infra/scripts/bootstrap-infisical-identity.sh`) that runs the
   `infisical` CLI against the running server to (a) create the initial
   admin (using server `INFISICAL_AUTO_BOOTSTRAP_*` env vars per research
   §2.2 auto-bootstrap evidence, OR via CLI signup — final mechanism is a
   proposal-phase open question), (b) create the bootstrap project,
   environment, sample secret, and Machine Identity, and (c) write the
   resulting UA credential as `Secret/infisical-operator-auth` in the
   operator namespace via `kubectl apply` directly (not via Git, not via
   SOPS). The Secret is **not committed** in any form because its existence
   depends on the server already running and creating the identity, and
   because rotation is owned by INIT-115, not INIT-103.

**Evidence**: research §6.2 (server root secrets exist before runtime sync;
operator credentials exist before runtime sync), §2.2 (env-var contract for
server; chart's auto-bootstrap fields exist as evidence of a supported
shape but were not validated end-to-end), §6.3 (first-run admin/project/
identity setup is required before Operator sync can succeed), §7.3
(bootstrap classification of server root secrets and operator credentials
is the proposal-phase open question being closed here), §1.3 (current SOPS
boundary forbids additional encrypted files without explicit allowlist
extension).

**Alternatives rejected**:
- Both secrets via SOPS-committed files: viable for server root, but the
  operator UA credential cannot be generated until the server is running,
  which forces a re-encrypt-and-commit step inside the bring-up flow that
  pollutes Git history with bootstrap byproducts and tangles INIT-103 with
  Git-write authority it does not own.
- Both secrets via direct `kubectl apply` (no SOPS): the server root must
  be reproducible across operators and clean cluster rebuilds; SOPS gives
  that reproducibility while keeping the boundary explicit. Manual creation
  drifts across operators and breaks INIT-102's channel-template-as-source-
  of-truth shape.
- Chart `autoBootstrap.enabled: true` writing `infisical-bootstrap-secret`
  (research §2.2): the chart-supported shape exists but research did not
  validate its end-to-end behavior; INIT-103 binds the explicit two-step
  delivery instead of relying on unverified chart automation.

**Consequence**: SLICE-103.04 owns the SOPS-encrypted server bootstrap file
and the post-server-startup identity bootstrap script. The SOPS boundary
linter must be extended to allow the new bootstrap file (D5). The operator
UA credential is intentionally absent from Git; the harness verifies its
presence in the cluster but never reads its values (D9). Because the UA
credential lives outside Git, every clean rebuild re-runs the identity
bootstrap script (idempotency required).

---

### D5 — D-SOPS-BOUNDARY-EXTEND

**Decision**: INIT-103 extends INIT-102's SOPS bootstrap boundary by adding
**exactly one** additional allowed encrypted file path:

```
gitops/bootstrap/infisical-server-bootstrap.enc.yaml
```

Updated allowlist for `infra/scripts/lint-sops-boundary.py`:

```python
ALLOWED_ENCRYPTED_FILES = {
    "gitops/bootstrap/sops-sentinel.enc.yaml",              # INIT-102 D5
    "gitops/bootstrap/infisical-server-bootstrap.enc.yaml", # INIT-103 D5
}
```

The runtime-secret-shaped key reject patterns established in INIT-102
(`infisical*`, `discord*token`, `password`, `secret_access_key`, `api_key`)
remain. They are refined to **whitelist the bootstrap-tier server keys
inside the new allowlisted file only**:

- Allowed inside `gitops/bootstrap/infisical-server-bootstrap.enc.yaml`:
  `ENCRYPTION_KEY`, `AUTH_SECRET`, `SITE_URL`, `DB_CONNECTION_URI`,
  `REDIS_URL`, and (if used) `INFISICAL_AUTO_BOOTSTRAP_EMAIL` /
  `INFISICAL_AUTO_BOOTSTRAP_PASSWORD`.
- Still rejected anywhere (including any addition to this file): per-tenant
  runtime secrets, Discord tokens, application DB credentials, application
  API keys, Operator UA credentials (`infisical*token`,
  `infisical*clientSecret`), MinIO/Vultr Object Storage credentials.

The encrypted-fields scope (`encrypted_regex: ^(data|stringData)$`) and the
`gitops/bootstrap/` directory containment rule are inherited unchanged.

**Evidence**: research §1.3 (current INIT-102 boundary forbids additional
encrypted files without explicit allowlist extension), §7.1, §7.2, §7.3
(server root secrets are bootstrap-classified because the server cannot
start without them; operator credentials are deliberately *not* in scope
because they are generated post-startup per D4). INIT-102 proposal §6 binds
the lint as a failing invariant, not a review convention; extending the
allowlist is the only authorized path.

**Alternatives rejected**:
- Allow any `gitops/bootstrap/*.enc.yaml`: drops the named-file invariant
  that makes the boundary auditable; future bootstrap files would slip in
  without explicit ratification.
- Add the operator UA credential to the allowlist: rejected by D4 (the
  credential is generated post-startup and not committed).
- Move runtime-secret guards into a per-file exclusion table: heavier than
  the current allowed-file-set + reject-pattern shape; not warranted by
  research evidence.

**Consequence**: SLICE-103.04 owns the linter change and a corresponding
test fixture. INIT-102's harness assertion that the lint fails on
non-allowlisted encrypted files (INIT-102 proposal §12) carries forward;
the INIT-103 harness adds a positive assertion that the new bootstrap file
decrypts successfully and produces the expected
`Secret/infisical-server-bootstrap`.

---

### D6 — D-INFISICAL-COMPONENTS

**Decision**: INIT-103 ships the following Infisical server components in
the local channel done state:

- **Backend application** (the standalone `infisical/infisical` image, which
  bundles backend + frontend per research §2.1).
- **PostgreSQL** in-cluster, PVC-backed (D7 below).
- **Redis** in-cluster, PVC-backed.
- **Infisical Operator** (D2).
- **Cluster-scoped CRDs** from the operator chart render (D2).
- **One `InfisicalSecret` CR** + its managed target Kubernetes Secret as the
  reconciliation proof (D9).

Deferred (explicitly not in INIT-103 done state):

- High-availability replicas (chart default `replicaCount: 2` per research
  §2.1, §2.3; INIT-103 pins `replicaCount: 1` for proof footprint).
- External managed PostgreSQL/Redis (production guidance per research §2.1,
  §2.3, §9.3; out of scope for first local proof).
- SMTP, telemetry, audit log shipping (research §9.3).
- `InfisicalPushSecret`, `InfisicalDynamicSecret`, `ClusterGenerator`,
  `Password`, `UUID` *exercise* (CRDs are installed per D2 but no CRs are
  authored in INIT-103; research §9.3).
- Workload auto-reload annotations (workloads owned by INIT-113; research
  §3.1, §9.3).
- Public ingress / TLS (owned by INIT-105; in-cluster Service URL only for
  INIT-103 — see D8).

**Evidence**: research §2.1 (component inventory), §2.3 (resource
footprint), §3.2 (CRD set), §9.3 (informational deferrals).

**Alternatives rejected**:
- Skip Redis: not supported by docs (research §2.1, §2.2 — Redis URL is
  required configuration).
- External managed Postgres/Redis for local: contradicts environment-
  agnostic memory (local self-hosts the same components as remote) and
  adds out-of-cluster dependencies INIT-103 does not own.
- Frontend as a separate Deployment: the standalone image bundles backend +
  frontend (research §2.1); a split shape adds without evidence.
- Author all six CRDs but cherry-pick controllers: rejected by D2.

**Consequence**: SLICE-103.02 owns the rendered server manifest set and
pins `replicaCount: 1` against the chart default. SLICE-103.05 authors a
single `InfisicalSecret` CR; downstream INITs add their own CRs without
changing INIT-103.

---

### D7 — D-DATA-PLANE

**Decision**: Infisical's local PostgreSQL and Redis run **in-cluster,
PVC-backed**, rendered from the upstream chart with PVC sizes pinned to
chart defaults (`8Gi` Postgres, `8Gi` Redis per research §2.1). Storage
class resolves to k3d's default storage class (`local-path` provisioner,
verified at harness time). This is INIT-103's Postgres for Infisical only;
INIT-111's application data plane Postgres is a distinct, later concern
and shares no resources with this instance.

**Evidence**: research §2.1, §2.3, §6.1. Self-hosted Infisical requires
Postgres and Redis (research §2.1, §2.2, §2.3). SQLite is not a documented
self-hosted storage option (research §2.3, §6.1). Helm chart defaults
provision in-cluster PVC-backed Postgres and Redis (research §2.1, §2.3),
with the explicit doc warning that the Postgres PVC contains encrypted
secrets and must not be deleted unless data loss is intended (research
§2.1). Environment-agnostic memory says local self-hosts the same
components as remote.

**Alternatives rejected**:
- SQLite: not documented by Infisical (research §2.3, §6.1).
- External managed Postgres/Redis: contradicts environment-agnostic
  memory and adds out-of-cluster dependencies INIT-103 does not own
  (research §6.1, §9.3).
- emptyDir / no PVC: the docs list unbound PVCs as a common pending-Pod
  cause and warn that Postgres data is stateful and security-sensitive
  (research §2.1, §2.3).
- Bundling INIT-103's Postgres with INIT-111's application Postgres: the
  Postgres images, schemas, and security boundaries differ; sharing would
  couple unrelated INITs (research §1.1 dependency ordering).

**Consequence**: SLICE-103.02 includes PVC manifests in the rendered output.
SLICE-103.06 (harness) asserts that both PVCs reach `Bound`, and that the
storage class is the expected default. Operators must not delete the
`infisical-system` namespace without first acknowledging Postgres data
loss.

---

### D8 — D-CHANNEL-SCHEMA-EXT

**Decision**: Add a top-level `infisical` block to both
`infra/schemas/platform-channel.schema.json` and the resolved channel
schema, with the following fields (all required when the block is present;
the block is required when `cluster.target == "k3d-local"`):

- `infisical.server_url` — base URL the Operator uses as `hostAPI`
  (e.g., `http://infisical.infisical-system.svc.cluster.local:8080` for
  k3d-local).
- `infisical.project_id` — Infisical project identifier
  (`secretsScope.projectId`).
- `infisical.environment` — Infisical environment slug
  (`secretsScope.envSlug`, e.g., `local`).
- `infisical.secrets_path` — root secrets path
  (`secretsScope.secretsPath`, default `/`).
- `infisical.auth_method` — enum `universal-auth` (only value accepted in
  INIT-103; `service-token` and `kubernetes-auth` reserved for future).
- `infisical.universal_auth_secret_name` — Kubernetes Secret name holding
  `clientId` + `clientSecret` (default `infisical-operator-auth`).
- `infisical.universal_auth_secret_namespace` — namespace of the credential
  Secret (default `infisical-system`).
- `infisical.operator_namespace` — namespace where the Operator runs
  (default `infisical-system`).
- `infisical.resync_interval` — `syncConfig.resyncInterval`
  (default `60s`).

Per-target conditionals:

- `cluster.target == "k3d-local"`: `infisical` block **required**; same
  shape as INIT-102's `gitops`-required-when-`k3d-local` pattern.
- `cluster.target == "vultr-vms"`: `infisical` block **optional** in
  INIT-103 (deferred until a remote-channel slice installs Flux + Infisical
  on the remote target, paralleling INIT-102's `gitops` treatment for
  `dev`).

`schema_version` remains `1` because the addition is additive and existing
valid `vultr-vms` channels remain valid without it (mirrors INIT-102 D7).

**Evidence**: research §5.1 (current schema baseline; strict additive
top-level block pattern), §5.2 (CRD-supported field enumeration with E23,
E35 citations), §5.3 (local self-hosts same components; remote is Vultr-
locked; per-channel endpoint config differs). DECISIONS.md D8 says channel
config carries Infisical endpoint. INIT-102 synthesis D7 establishes the
"strict additive top-level block, required for `k3d-local`, optional for
`vultr-vms`" pattern that INIT-103 reuses verbatim.

**Alternatives rejected**:
- `project_slug` instead of `project_id`: both are CRD-supported (research
  §3.3, §5.2); `project_id` is more stable across project renames and
  matches the binding "explicit `project_id`" from research §4.2.
- A separate `auth` sub-object containing nested `universal_auth.*` fields:
  flatter shape matches INIT-102's `gitops` block (no nested objects);
  consistency wins.
- `service-token` accepted as a valid `auth_method` value in INIT-103: D3
  binds UA only; accepting other values now would let bad config through
  schema validation.
- Separate `infisical/channels/*.yaml` file: violates channel-template
  single-source-of-truth (INIT-102 synthesis D7 rejected the analogous
  split for `gitops`).

**Consequence**: SLICE-103.03 owns the schema change, resolver updates,
fixture additions, and validator tests. The resolved channel JSON feeds
both the rendered `InfisicalSecret` CR and any per-channel substitution in
the server install (e.g., `SITE_URL`). The `infisical.server_url` is a
cluster-internal Service URL until INIT-105 ships DNS/TLS; remote exposure
is a later handoff (research §5.3).

---

### D9 — D-LOCAL-CONTRACT

**Decision**: "Real local Infisical reconciliation" is proven by the
following six harness assertions, run in order against a live k3d cluster
that has already passed INIT-102's substrate harness:

1. `Deployment/infisical` in `infisical-system` reports
   `.status.availableReplicas == .spec.replicas` (= 1 per D6).
2. The chart-rendered Postgres workload in `infisical-system` is Ready and
   `PVC/<infisical-postgresql-data>` is `Bound`. Same assertion for
   `infisical-redis`. Exact resource names follow the chart render and are
   pinned in SLICE-103.02.
3. `Deployment/<infisical-secrets-operator>` (operator chart name) in
   `infisical-system` reports `.status.availableReplicas == .spec.replicas`.
4. `Secret/infisical-operator-auth` in `infisical-system` exists and
   contains non-empty `clientId` and `clientSecret` keys (values not
   logged).
5. `InfisicalSecret/infisical-local-sample` in namespace `infisical-sample`
   reports `status.conditions[type=Ready].status == "True"` with current
   `observedGeneration`.
6. `Secret/infisical-local-sample` in namespace `infisical-sample` exists
   and contains key `INFISICAL_SAMPLE_KEY` decoding to value
   `infisical-local-ready` (the deterministic seed value the bootstrap
   script wrote into the Infisical project at path `/sample`, environment
   `local`).

The bootstrap script (`infra/scripts/bootstrap-infisical-identity.sh`)
must run between (1)–(2) and (3)–(6); it provisions the admin user, the
`platform` organization, the `local` project, the `local` environment, the
sample secret at `/sample/INFISICAL_SAMPLE_KEY=infisical-local-ready`, the
Machine Identity, and the UA credential applied as
`Secret/infisical-operator-auth`.

**Evidence**: research §6.4 (real reconciliation proof must include server
ready, operator ready, `InfisicalSecret` CR, target Kubernetes Secret),
§3.1, §3.3 (`managedKubeSecretReferences` defines target Secret delivery),
§6.3 (first-run admin/project/identity required before Operator sync can
succeed), §6.1 (PVC binding is a documented common failure mode and must
be asserted). INIT-102 proposal §12 sets the precedent for live-cluster
assertions over render-only checks.

**Alternatives rejected**:
- Render-only verification (`flux build` / `kustomize build`): forbidden by
  D8 environment-agnostic frame and INIT-102 D11 precedent.
- Skip the sample-Secret round-trip and assert only Operator readiness:
  leaves the runtime sync path unverified end-to-end.
- Read the operator UA Secret values: leaks bootstrap material into harness
  logs without strengthening the proof.
- Exercise `InfisicalPushSecret` or `InfisicalDynamicSecret`: deferred per
  D6.

**Consequence**: SLICE-103.06 owns the harness extension. The harness
script is layered on top of `infra/tests/validate_gitops_substrate.sh` from
INIT-102; it does not duplicate INIT-102 assertions. The bootstrap script
must be idempotent (re-running it on an already-bootstrapped server is a
no-op).

---

### D10 — D-INIT-104-HANDOFF

**Decision**: INIT-104 (object storage: MinIO local + Vultr Object Storage
remote) consumes Infisical via:

- **Project**: `platform-storage` (separate from the `local` bootstrap
  project to keep the storage credential surface namespaced).
- **Environment**: per-channel envSlug (`local` for k3d-local; future
  remote envSlug for Vultr-VM channels).
- **Secrets path**: `/object-storage` (channel-target-agnostic; the
  contained keys differ per target).
- **Authentication**: same UA pattern as D3, with INIT-104 either reusing
  the INIT-103-bootstrapped UA credential or provisioning its own Machine
  Identity scoped to `platform-storage`. INIT-103 binds the *interface*
  (UA + project/env/path); INIT-104 binds the identity scoping decision.
- **Expected keys per environment**:
  - Local (k3d): `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`.
  - Remote (Vultr): `VULTR_OS_ACCESS_KEY`, `VULTR_OS_SECRET_KEY`.
- **Operator namespace**: `infisical-system` (D8 default); INIT-104
  authors `InfisicalSecret` CRs in its own application namespace
  (e.g., `minio-system`) referencing the operator namespace by the channel
  schema's `infisical.operator_namespace` field.

INIT-103 does **not** create the `platform-storage` project, the storage
secrets, or the INIT-104 `InfisicalSecret` CR. INIT-104 owns those.
INIT-103 only guarantees the contract surface they will consume.

**Evidence**: research §1.1 (INIT-104 depends on INIT-103 for MinIO
credentials through Infisical; INIT-111 depends on INIT-103 for DB
credentials; INIT-113 depends on INIT-103 for workload secrets), §10
(SLICE-103.07 documentation and INIT-104 handoff), §3.3 (CRD-level support
for project/env/path scoping), §5.2 (channel schema fields supporting
multi-project usage by downstream INITs).

**Alternatives rejected**:
- Single shared project for all consumers: collapses tenant boundaries
  ahead of INIT-116 and forces every later INIT to reason about cross-
  project secret leakage.
- INIT-103 pre-creating the `platform-storage` project: violates ownership
  (the storage project's content is INIT-104's concern), and INIT-103
  cannot anticipate every consumer's project shape.
- Tying INIT-104 to a different auth method (service token / Kubernetes
  Auth): inconsistent with D3 and forces INIT-104 to ship its own
  identity-bootstrap path.

**Consequence**: SLICE-103.07 documents this handoff in `gitops/README.md`
and `infra/README.md`. INIT-104's proposal phase consumes this binding;
INIT-103 ships nothing INIT-104-specific.

---

### D11 — D-VERSION-PINS

**Decision**: Pinned versions (latest stable as of 2026-04-26):

- **Infisical server image**: `infisical/infisical:v0.151.0` — chart-docs
  reference value (research §2.1); confirmed the stable choice for
  INIT-103; re-pin is an explicit edit. Implementation must verify against
  latest GitHub releases at render time and document the verified tag in
  the rendered manifest filename or annotation.
- **Infisical Kubernetes Operator image**:
  `infisical/kubernetes-operator:v0.10.32` — latest tagged release on
  2026-04-26 (research §3.5). The chart's `values.yaml` shows manager image
  `v0.10.31` against chart `v0.10.32` (research §3.5); implementation
  verifies which image actually deploys and pins the verified tag,
  defaulting to `v0.10.32` if the values mismatch is a chart bug.
- **Infisical Operator chart**: chart version `v0.10.32` (rendered into
  raw manifests at implementation time).
- **Infisical server chart**:
  `infisical-helm-charts/infisical-standalone` at the latest stable chart
  version available on 2026-04-26 (verify at render time; pin in the
  rendered manifest filename or annotation).
- **PostgreSQL image**: `postgres:14-alpine` — matches the upstream Docker
  Compose evidence (research §2.1, §2.3) and is the chart's documented
  Postgres major.
- **Redis image**: `redis:7-alpine` — explicit version pin replaces the
  upstream Compose's bare `redis` (research §2.1) for reproducibility.
- **Infisical CLI** (used by `bootstrap-infisical-identity.sh`):
  `v0.43.78` — latest as of 2026-04-24 (research §8.2, E34, E37). Added to
  `infra/scripts/install-cluster-tools.sh` alongside INIT-102's tool pins.
- **Helm CLI** (implementation-time only; not installed in cluster, used
  only to render upstream charts to raw committed manifests): pin to
  latest stable `v3.x` at implementation time. Helm is a render-time tool,
  not a runtime tool, so its presence in `install-cluster-tools.sh` is
  optional rather than required for cluster bring-up.

**Evidence**: research §2.1 (server image and Postgres tag), §3.5
(operator chart and image evidence including version mismatch), §8.1
(local toolchain availability snapshot), §8.2 (latest Infisical CLI
v0.43.78 on 2026-04-24), §9.2 (need to verify exact image tags at
implementation time because docs example `v0.151.0` may lag latest).

**Alternatives rejected**:
- `infisical/infisical:latest`: explicitly warned against by chart docs
  (research §2.1).
- `bitnamilegacy/postgresql` chart-bundled image: viable but heavier; the
  upstream Compose's `postgres:14-alpine` is sufficient, smaller, and a
  documented contract (research §2.1, §2.3).
- Pin chart but float image tags: defeats reproducibility; raw committed
  manifests must encode every image tag explicitly.

**Consequence**: SLICE-103.01 (toolchain) installs the Infisical CLI pin.
SLICE-103.02 (server render) commits the verified server image tag.
SLICE-103.01 (operator render) commits the verified operator image tag.
The harness asserts the running images match the pinned tags at run time
(prevents drift if a chart re-render changes a default).

---

## Anti-scope (binding)

INIT-103 explicitly does **not** do any of the following. Each item is
deferred to the named successor or out of scope entirely.

- **Crossplane**, control-cluster Crossplane provider/configuration, and
  any application-cluster provisioning (INIT-106).
- **Object storage** (MinIO local, Vultr Object Storage remote, S3
  buckets, bucket lifecycle, `InfisicalSecret` CRs for storage
  credentials): INIT-104.
- **cert-manager**, **DNS automation**, **TLS issuance**, ingress
  controllers, and public Infisical exposure (INIT-105 / INIT-110).
- **Application data plane** Postgres (the application database, distinct
  from INIT-103's Infisical Postgres): INIT-111.
- **Application workloads** (Discord daemon, API service, beta-guild
  runtime, workload `InfisicalSecret` CRs other than the INIT-103 sample
  proof): INIT-113.
- **Auth** (Authentik, OIDC, OPAL/Cedar policy, Pomerium routes): INIT-114.
- **Access policy** for Infisical itself, age key rotation, Operator
  credential rotation, break-glass: INIT-115.
- **Tenant isolation**, namespace boundary model, per-tenant
  `InfisicalSecret` delegation, Operator namespace scoping
  (`scopedNamespaces` / `scopedRBAC`): INIT-116.
- **Observability**, notifications, alerts, dashboards, OTLP collectors,
  Flux `notification-controller`: INIT-117.
- **CI/CD**, Buildkite agents, image build/push: INIT-108 / INIT-109.
- **Backup/restore** for the Infisical Postgres PVC: INIT-112.
- **`HelmRelease`** reconciliation and `helm-controller`: forbidden by
  INIT-102 D2.
- **`OCIRepository`-backed sources** for Infisical manifests: INIT-102
  wires only `GitRepository`.
- **Remote `dev`/Vultr-VM channel** Infisical installation: deferred until
  remote Flux is wired (paralleling INIT-102's `dev` deferral).
- **High-availability** Infisical server (multi-replica), **external
  managed Postgres/Redis**: deferred (research §2.1, §9.3).
- **`InfisicalPushSecret`**, **`InfisicalDynamicSecret`**,
  **`ClusterGenerator`**, **`Password`**, **`UUID`** *exercise* (CRDs
  installed per D2, but no CRs authored).
- **Workload auto-reload** annotations (deferred to consumer INITs).
- **SMTP**, telemetry, audit log shipping for Infisical (research §9.3).
- **Multi-project** seeding (the only INIT-103-created project is the
  `local` bootstrap project; all other projects are owned by their
  consumer INITs per D10).
- **Runtime secrets in SOPS** of any kind (boundary inherited from INIT-102
  D5; the D5 extension here is bootstrap-tier only).

## Open questions (to resolve in proposal phase)

- **Bootstrap script ordering**: exact placement of
  `bootstrap-infisical-identity.sh` relative to Flux's first reconcile —
  whether it runs as a Kubernetes `Job` reconciled by Flux (gated on
  server readiness) or as a host-side step in `bring-up-local-channel.sh`
  after the server Pod is Ready but before the operator `InfisicalSecret`
  is applied.
- **Server `INFISICAL_AUTO_BOOTSTRAP_*` env vars vs. CLI bootstrap**:
  whether to use the chart's auto-bootstrap fields (research §2.2,
  unverified) for admin creation, or to drive everything through
  `infisical user create`-style CLI calls. D4 binds the *outcome*; the
  *mechanism* inside the bootstrap script is a proposal-phase choice.
- **Helm install shape**: whether `helm` is added to
  `install-cluster-tools.sh` as a required cluster tool (so any operator
  can re-render upstream charts) or kept as an implementation-only tool
  documented in `infra/README.md`.
- **Namespace layout**: whether server, operator, and sample workload
  share one `infisical-system` namespace or split into `infisical-system`
  (server + operator) and `infisical-sample` (the proof workload). D9
  assumes the split; the proposal must confirm.
- **Render source for the server**: chart vs. authored-from-env-contract
  (research §2.4 leaves both viable). D1 binds chart-render; the proposal
  documents the render command and the chart values overrides.
- **Operator scope**: cluster-wide watch (chart default per research §3.4)
  vs. `scopedNamespaces` to `infisical-sample`. D6 leaves cluster-wide
  acceptable for INIT-103; INIT-116 owns the eventual scoping. The
  proposal confirms.
- **Storage class assertion**: whether the harness pins the expected
  storage class name (`local-path` for k3d) or accepts any default. D9
  assumes the default; explicit pin would catch drift earlier.
- **Sample-secret seed value source**: whether `infisical-local-ready` is
  hard-coded in the bootstrap script (current binding) or carried in the
  channel YAML for parity with INIT-102's sentinel ConfigMap shape.
- **First-run idempotency model**: how `bootstrap-infisical-identity.sh`
  detects "already bootstrapped" — by querying the Infisical API for the
  organization/project, by checking for the `Secret/infisical-operator-auth`
  in-cluster, or both.

---

**File**: `worktrees/init-103-infisical-runtime-secrets/.pipeline/synthesis.md`
