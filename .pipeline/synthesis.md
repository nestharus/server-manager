# INIT-104 Synthesis

This synthesis binds INIT-104's design decisions before the proposal phase.
Each D-record names the decision, the research evidence supporting it, the
alternatives rejected, and the consequence for the proposal phase and
downstream INITs. Synthesis is grounded in research only; no decision below
introduces design specifics beyond what is needed to bind the choice.

Source: `worktrees/init-104-object-storage/.pipeline/research.md` (sections
referenced as `research §N.M`; evidence ids referenced as `[E#]`). Binding
priors:

- INIT-103 proposal `worktrees/init-103-infisical-runtime-secrets/.pipeline/proposal.md` (channel `infisical` block, sample sync proof).
- INIT-103 implementation `worktrees/init-103-infisical-runtime-secrets/.pipeline/implementation.md` §INIT-104 Handoff (object-storage credential contract, project `platform-storage`, path `/object-storage/<channel>/...`).
- INIT-102 proposal `worktrees/init-102-gitops-substrate/.pipeline/proposal.md` D2 (Flux components: only `source-controller` + `kustomize-controller`; no `helm-controller`, no `HelmRelease`).
- `DECISIONS.md` D8 (local-as-first-deployment, k3s everywhere, Infisical runtime, channels, real-local done state, MinIO survives only as the local S3 backend with Vultr Object Storage as the remote).
- `~/.claude3/projects/-home-nes-projects-server-manager/memory/environment-agnostic-stack.md` (same stack runs locally and remotely; per-channel YAML carries provider/endpoint/credential differences).

## Decision Records

### D1 — D-MINIO-INSTALL

**Decision**: INIT-104 installs MinIO into the local k3d channel as **raw
authored Kustomize manifests** under
`gitops/channels/local/object-storage/minio/`, in the shape of a
single-node `Deployment` (or `StatefulSet` with `replicas: 1`) plus a
`PersistentVolumeClaim`, a `ClusterIP` `Service` exposing the API port, the
namespace, and a Kubernetes `Secret` materialised by the storage
`InfisicalSecret` (D4). The MinIO Operator/Tenant path and the community
Helm chart are not used. The first-party AIStor Operator chart is not
used.

**Evidence**: research §2.1 (three packaging shapes documented: raw
manifests, community chart, Operator) [E38, E39, E40, E42], §2.2 (local
done state needs only a real S3-compatible endpoint, not HA durability;
single-node container shape is documented for development/evaluation;
INIT-102 substrate has source-controller + kustomize-controller only and
no Helm controller; current local channel reconciliation is plain
Kustomize, not HelmRelease) [E2, E4, E11, E17, E20, E25, E38, E39, E40,
E42], §10.3 (the lowest-moving-parts local shape is namespace + Secret +
PVC + workload + Service + post-readiness bucket Job; raw shape matches
the existing Flux substrate) [E16, E17, E25, E26, E41, E43, E44].
Reinforced by INIT-102 D2 forbidding `helm-controller`/`HelmRelease`.

**Alternatives rejected**:
- MinIO Operator + Tenant CRDs: brings Operator-managed CRDs and
  AdminJob machinery and the AIStor Operator chart requires a license
  value; net moving parts exceed the proof contract (research §2.1
  [E39, E40, E45]).
- Community Helm chart rendered to YAML: the README explicitly says the
  chart is community maintained and not guaranteed by MinIO, and its
  defaults (16Gi memory request, 500Gi PVC) are oversized for local k3d
  (research §2.1, §2.3 [E42, E43]). Rendering to raw YAML is also
  redundant against authored manifests for a single-Pod local proof.
- AIStor Operator + AIStor object-store chart: requires a license value
  (research §2.1 [E40]); not justified for the local proof contract.

**Consequence**: INIT-104 owns and reviews the MinIO manifests directly.
Upgrades are an explicit re-author or re-pin in tree, not a runtime fetch
(matches the INIT-103 render-and-commit precedent). No new Flux
components or CRDs are introduced. The proposal phase must specify the
exact workload kind (`Deployment` vs `StatefulSet`), a local-appropriate
PVC size, resource requests/limits compatible with the one-server/one-agent
local k3d shape (research §2.3 [E21, E42, E43]), and probe shapes.

---

### D2 — D-MINIO-COMPONENTS

**Decision**: For the local channel, INIT-104 ships **MinIO API only**:
the server process exposing the S3-compatible API on port `9000` through a
`ClusterIP` `Service`. The MinIO Console is **not** deployed in INIT-104.
No `Ingress`, no `LoadBalancer`, no host-network exposure.

**Evidence**: research §2.4 (API port `9000`, console port `9001`, both
supported as ClusterIP; the requested internal endpoint
`http://minio.minio-system.svc.cluster.local:9000` matches ClusterIP API
on port 9000) [E16, E43], §7.1 (console exposure is optional for local
proof; evidence requires API round-trip only) [E4, E11, E43], §9.3
INFORMATIONAL (Console can remain internal unless a later route/ingress
initiative exposes it) [E43].

**Alternatives rejected**:
- Server + Console exposed on `9001`: not required by the local proof
  contract; pulls in a second Service and port surface that no INIT-104
  consumer needs (research §7.1 [E4, E11, E43]).
- Public Console exposure: gated by ingress and TLS work that is INIT-105
  / later, and out of scope here (D11 below).

**Consequence**: The local proof asserts only the API path. If a future
initiative needs the Console, it adds a second Service and (when
needed) ingress without re-shaping INIT-104.

---

### D3 — D-BUCKET-CREATION

**Decision**: Initial bucket creation for the local channel is a
**post-readiness Kubernetes `Job`** in `minio-system` that runs the
official MinIO `mc` client image with `mc alias set` followed by
`mc mb --ignore-existing` against the in-cluster MinIO Service. The Job
is reconciled by Flux as part of the channel overlay, idempotent on
re-apply, and creates exactly one sample bucket (D9). Init containers
embedded in the MinIO Pod and the Operator `AdminJob` are not used. The
community-chart `makeBucketJob` is not used (D1 excludes the chart).

**Evidence**: research §2.5 (`mc mb` creates buckets on MinIO and other
S3-compatible services; supports `--ignore-existing` for idempotent jobs;
a non-Operator raw manifest path can use an ordinary Kubernetes Job
running `mc` after readiness) [E43, E44], §10.3 (post-readiness bucket
Job is the lowest-moving-parts mechanism that fits the existing Flux
substrate) [E16, E17, E25, E26, E41, E43, E44], §9.3 INFORMATIONAL (S3
PUT does not auto-create buckets; bucket creation is explicit) [E44, E47,
E55], §2.5 (Operator `AdminJob` requires the Operator path, which D1
rejects) [E45].

**Alternatives rejected**:
- Init container on the MinIO Pod: couples bucket bootstrap to the data
  Pod's lifecycle, blocks readiness, and violates idempotent re-apply
  semantics on `mc` failure modes (research §2.5 [E43, E44]).
- Operator `AdminJob`: requires the Operator path that D1 rejects
  (research §2.5 [E45]).
- Boto3 / `aws s3 mb` Job: feasible against the same API (research §3.4,
  §4.1 [E48, E55, E56, E57]), but `mc mb --ignore-existing` is the
  documented idempotent primitive; choosing one image keeps the bucket
  Job's tool surface narrow.
- Sample round-trip script as the bucket creator: the harness round-trip
  (D9) asserts state; it does not create state in production paths.

**Consequence**: INIT-104 introduces `mc` to two surfaces: the in-cluster
bucket Job image (D11) and the host toolchain (D12). The Job authenticates
with the MinIO root credentials synced by D4. The proposal phase must
choose whether the Job runs once at install or as a `Job` re-applied by
Flux on each reconcile cycle (idempotent either way under
`--ignore-existing`), and must specify the readiness wait mechanism
(initContainer netcat / `mc ready` / explicit `kubectl wait` pre-step).

---

### D4 — D-CREDENTIAL-FLOW

**Decision**: Object-storage credentials flow exclusively through Infisical
via an `InfisicalSecret` custom resource per channel, materialising into a
Kubernetes `Secret` consumed by MinIO and any in-cluster client (e.g., the
bucket Job in D3). For the local channel, the binding is:

- Infisical project: `platform-storage`.
- Infisical environment: `local`.
- Infisical path: `/object-storage/local/`.
- Infisical secret keys: `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`.
- Target Kubernetes `Secret` namespace: `minio-system`.
- Target Kubernetes `Secret` name: `minio-root` (one canonical name; the
  exact key casing inside the Secret matches the Infisical key names so
  MinIO's `envFrom`/`env` references resolve directly).
- Universal Auth source for the storage `InfisicalSecret`: a dedicated
  INIT-104 Machine Identity (see D5), not the INIT-103
  `infisical-operator-auth` UA.
- `creationPolicy: Owner` on the `InfisicalSecret`, matching the proven
  INIT-103 pattern.
- `InfisicalSecret` layout: **one CR per provider key set per channel**
  (recursive sync over the channel-scoped path, with that path containing
  exactly the intended keys). Splitting MinIO keys vs Vultr keys across
  channels is a per-channel matter, not multiple CRs in the same channel.

**Evidence**: research §1.3 (INIT-103 handoff binds project
`platform-storage`, path `/object-storage/<channel>/...`, local keys
`MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD`, expected local consumer namespace
`minio-system`) [E16], §5.1, §5.2 (project/environment/path sync mechanics
proven by the INIT-103 sample; existing CR pattern uses
`secrets.infisical.com/v1alpha1`, `credentialsRef.secretName` /
`secretNamespace`, and `creationPolicy: Owner`) [E16, E26, E27, E28],
§5.4 (object-storage credentials are runtime-only Infisical data and the
SOPS linter would reject them if they ever appeared in `gitops/bootstrap/`)
[E16, E17, E19, E29, E30], §6.2 (candidate channel fields:
`credentials_secret_name`, `credentials_secret_namespace`, `infisical_path`)
[E16].

**Alternatives rejected**:
- SOPS-encrypted Kubernetes Secret for MinIO root: forbidden by D8 and the
  SOPS linter's runtime-secret-shaped rejection rules; `MINIO_ROOT_PASSWORD`
  matches the linter's reject pattern (research §5.4 [E16, E17, E19,
  E29, E30]).
- Hardcoded literal credentials in any Kustomize resource: same boundary.
- One recursive `InfisicalSecret` covering both MinIO and Vultr keys at
  `/object-storage/`: collapses environment scoping, defeats per-channel
  parameterization, and contradicts the channel-id-as-environment shape
  in the handoff (research §1.3 [E16]).
- `includeAllSecrets: true` over `/object-storage/` (the parent): pulls
  cross-channel keys into a single Secret; rejected for the same reason.

**Consequence**: INIT-104 authors `InfisicalSecret` resources at
`gitops/channels/local/object-storage/infisical/` (or a sibling location
under `gitops/channels/local/object-storage/`). The MinIO Pod consumes
`Secret/minio-root` via `envFrom: secretRef: name: minio-root`. The
bucket Job consumes the same Secret. No application code reads MinIO
root credentials; application credentials are out of scope for INIT-104
and are deferred to INIT-115 (D11).

---

### D5 — D-INFISICAL-BOOTSTRAP

**Decision**: Local Infisical seeding is extended by a **new sibling
script** to `infra/scripts/bootstrap-infisical-identity.sh` —
`infra/scripts/bootstrap-infisical-storage.sh` — invoked by
`infra/scripts/bring-up-local-channel.sh` after the Infisical server is
ready and after the INIT-103 identity bootstrap. The new script is
idempotent and:

1. Creates project `platform-storage` if absent.
2. Ensures environment `local` exists in that project.
3. Creates folder `/object-storage/local/` if absent.
4. Seeds initial values for `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`
   under that path, generating cryptographically strong values on first
   run; subsequent runs leave existing values in place (idempotent).
5. Creates a dedicated INIT-104 Machine Identity scoped to
   `platform-storage`, mints its Universal Auth credentials, and writes
   them into a Kubernetes Secret in `infisical-system` with a name
   distinct from the INIT-103 UA Secret (e.g.,
   `infisical-storage-operator-auth`).

A dedicated sibling script (rather than extending
`bootstrap-infisical-identity.sh`) keeps INIT-103's identity-bootstrap
surface unchanged and matches its single-responsibility shape.

**Evidence**: research §5.1 (project `platform-storage` is bound but
unbootstrapped today; current local sample is in `platform-local`)
[E16, E26, E27], §1.3 (INIT-104 has an open choice between reusing
INIT-103 UA or creating an INIT-104-owned Machine Identity; UA Secret
not added to `gitops/bootstrap/`) [E16, E17], §1.2 (INIT-103 bootstrap
is channel-driven and idempotent; provides the template) [E15, E26, E27,
E28], §9.2 BLOCKS_IMPLEMENTATION (bootstrapping `platform-storage` is a
prerequisite of INIT-104 implementation) [E16, E27, E28].

**Alternatives rejected**:
- Reuse `infisical-operator-auth` for storage sync: violates least
  privilege — INIT-103's UA is scoped to `platform-local`; a UA scoped
  to `platform-storage` is the correct seam (research §5.1 [E16]).
- Extend `bootstrap-infisical-identity.sh` in place: bloats the
  identity-bootstrap responsibility and couples INIT-104 changes to
  INIT-103's contract (research §1.2 [E28]).
- Store storage credentials in `gitops/bootstrap/` SOPS files: forbidden
  by D4 and the SOPS linter (research §5.4 [E16, E17, E29, E30]).

**Consequence**: `infra/scripts/bring-up-local-channel.sh` and the
local-cluster harness gain a new pre-Flux step. The harness asserts
that the Machine Identity Secret exists in `infisical-system` and the
storage `InfisicalSecret` reaches `Ready` (D9). The remote channel's
storage credential seeding is owned by the operator runbook for that
channel (D7), not by `bootstrap-infisical-storage.sh` (which is local).

---

### D6 — D-S3-SDK-CONTRACT

**Decision**: The same-S3-SDK contract for application code and harness
clients is the five-tuple **(endpoint, region, access_key, secret_key,
bucket)**, sourced from a Kubernetes Secret per consumer namespace.
The Secret keys are exactly:

```
S3_ENDPOINT_URL    # e.g., http://minio.minio-system.svc.cluster.local:9000 (local)
S3_REGION          # e.g., us-east-1
S3_ACCESS_KEY_ID   # provider-agnostic alias
S3_SECRET_ACCESS_KEY
S3_BUCKET          # e.g., humility-local-sample (local)
```

For the **local proof only**, the application-facing Secret may equal
`Secret/minio-root` (root credentials) under the endpoint/bucket envs
above; least-privilege application keys are deferred to INIT-115.
INIT-104 only ships the **MinIO root** Secret materialisation (D4). The
canonical application-facing Secret name is `s3-credentials` per consumer
namespace, but INIT-104 does not create application-namespace Secrets;
that mapping is owned by INIT-111/112/113 consumers.

**Evidence**: research §3.3 (Boto3 supports `endpoint_url`, `region_name`,
`aws_access_key_id`, `aws_secret_access_key`; AWS CLI supports
`--endpoint-url`; Vultr requires HTTPS + Signature V4) [E47, E50, E55,
E56, E57], §4.1 (one app SDK path; Boto3 covers MinIO + Vultr;
`mc`/AWS CLI cover proof) [E32–E34, E42, E44, E48, E55, E56, E57], §4.4
(common minimum config = endpoint + access key + secret key + region +
bucket; app code does not branch on provider) [E16, E47, E56, E57],
§9.4 (open: addressing style; open: app credentials vs root) [E16, E41,
E43, E47, E57].

**Alternatives rejected**:
- Provider-prefixed env names (`MINIO_ROOT_USER` / `VULTR_OS_ACCESS_KEY`)
  in application config: leaks provider identity into application code
  and violates the "same SDK code" parity in
  `environment-agnostic-stack.md` and D8 (research §1.1 [E2, E3, E9,
  E10]). The provider-prefixed names exist in **Infisical key names**
  for clarity at the secret-store boundary (D4), but consumers see the
  generic `S3_*` aliases.
- Two SDKs (one for MinIO, one for Vultr): redundant; Boto3 covers both
  (research §3.3, §4.1).
- Auto-detect addressing style per endpoint: the proposal phase pins
  addressing style to **path-style for the local MinIO endpoint** and
  **virtual-host style for the Vultr endpoint** via SDK config carried
  in channel YAML; `auto` is rejected because behaviour differs across
  SDK versions (research §3.3 [E47, E57]).

**Consequence**: The harness round-trip (D9) and any later application
client read `S3_*` env vars from a single Secret. Channel YAML carries
addressing-style and region per channel (D7). INIT-104 does not add an
application S3 wrapper; the wrapper lands when INIT-111/112/113 first
need it, with the SDK contract above.

---

### D7 — D-CHANNEL-SCHEMA-EXT

**Decision**: A new top-level `object_storage` block is added to both
`infra/schemas/platform-channel.schema.json` and
`infra/schemas/platform-channel-resolved.schema.json`,
`additionalProperties: false`, alongside the existing `cluster`, `state`,
`gitops`, and `infisical` blocks. `schema_version` remains `1`; the
addition is purely additive. Required fields:

```
provider                      enum: ["minio", "vultr-os"]
endpoint                      uri
region                        string
addressing_style              enum: ["path", "virtual"]
bucket                        string (canonical sample/app bucket for the channel)
infisical_project             string (default: "platform-storage")
infisical_environment         string (defaults to channel id)
infisical_secrets_path        string (default: "/object-storage/<channel>/")
universal_auth_secret_name    string (default: "infisical-storage-operator-auth")
universal_auth_secret_namespace string (default: "infisical-system")
credentials_secret_name       string (default: "minio-root" local; "vultr-os" remote)
credentials_secret_namespace  string (default: "minio-system" local)
```

Per-target conditionals:

- `cluster.target == "k3d-local"` requires `gitops`, `infisical`,
  **and `object_storage`**, with `object_storage.provider == "minio"`,
  `endpoint` matching the cluster-internal pattern
  `^http://minio\..*\.svc\.cluster\.local:9000$`, and
  `addressing_style == "path"`.
- `cluster.target == "vultr-vms"` makes `object_storage` **optional**
  in INIT-104 (consistent with INIT-103's treatment of `infisical` for
  remote). When present, `provider == "vultr-os"` and `endpoint` must
  match `^https://[a-z]{3}1\.vultrobjects\.com$`,
  `addressing_style == "virtual"`.

`infra/scripts/resolve_platform_channel.py`,
`infra/scripts/validate_platform_channels.py`, and
`infra/channels/fixtures/local-child.yaml` are extended to validate
inherited `object_storage` fields under the same channel-resolution
pattern INIT-103 uses for `infisical`.

**Evidence**: research §6.1 (existing schema is strict
`additionalProperties: false`; local conditional already requires
`gitops`/`infisical`; resolver already validates inherited Infisical
fields) [E20, E23, E24, E28], §6.2 (candidate fields and conditionals
itemised) [E2, E6, E16, E21, E22, E43, E47, E50, E51, E56], §6.3 (open:
required for every channel vs `k3d-local` first; open: bucket prefix
shape) [E10, E21, E22, E35], §3.2 (Vultr endpoint pattern
`<region>1.vultrobjects.com`) [E47, E50, E51], §1.4 (no
`object_storage` in current local or dev YAML) [E21, E22].

**Alternatives rejected**:
- Bump `schema_version` to `2`: not warranted; addition is additive
  with conditional requirements (research §6.1 [E23, E24]).
- Require `object_storage` for `vultr-vms` in INIT-104: current `dev`
  channel lacks GitOps/Infisical, so the storage block has no
  reconciler to consume it yet (research §5.3, §6.3 [E22]). Remote
  enforcement lands when remote GitOps lands.
- Store `infisical_path` as channel-derived only (no field): hides a
  validatable invariant that the channel id appears in the path
  (research §6.2 [E16, E21, E22]); explicit field with pattern
  validation is stronger.
- Store credentials inline in channel YAML: forbidden by D4.

**Consequence**: `infra/channels/local.yaml` gains a concrete
`object_storage` block; `infra/channels/dev.yaml` may add an aspirational
block but does not have to. Tests under `infra/tests/` add schema
positive/negative cases. Pattern validations document the local
in-cluster Service URL and the Vultr regional endpoint shape.

---

### D8 — D-VULTR-OS-CONTRACT

**Decision**: For `vultr-vms` channels, the remote object-storage
contract is:

- **Endpoint**: `https://<region>1.vultrobjects.com`, where `<region>`
  is the three-letter Vultr region prefix that matches the channel's
  declared cluster region (e.g., `ewr1.vultrobjects.com` for region
  `ewr`).
- **Addressing style**: virtual-host.
- **Auth**: S3 access key + secret key, Signature V4, HTTPS only.
- **Credentials**: stored in Infisical at
  `/object-storage/<channel>/VULTR_OS_ACCESS_KEY` and
  `/object-storage/<channel>/VULTR_OS_SECRET_KEY`, materialised by an
  `InfisicalSecret` into a Kubernetes Secret in the consumer namespace
  for that channel.
- **Subscription / bucket provisioning**: out of band of INIT-104's
  Flux/Kustomize path. Bucket creation for remote channels is owned
  by the operator runbook, executed via Vultr Console, `vultr-cli`, or
  the `vultr_object_storage` Terraform resource. INIT-104 does **not**
  ship Terraform for Vultr OS subscriptions.
- **Documentation only in INIT-104**: the remote contract is documented
  in `infra/README.md` and `gitops/README.md`. No remote `Flux` /
  `InfisicalSecret` resources are committed for `vultr-vms` channels in
  INIT-104.

**Evidence**: research §3.1, §3.2 (provisioning paths: Console / API /
CLI / Terraform; endpoint pattern; region examples; current `dev`
channel uses `ewr`) [E22, E46, E47, E49, E50, E51], §3.3 (auth, S3
keys, HTTPS, Signature V4) [E16, E47, E50], §3.4 (compatibility matrix
supports Create/Put/Get/Delete/List; bucket name limits 3–63 chars;
default 100-bucket subscription limit) [E48, E53], §5.3 (remote
channel GitOps/Infisical install is currently omitted in `dev`, so
remote apply remains outside INIT-104 local proof) [E16, E22, E26].

**Alternatives rejected**:
- Ship `vultr_object_storage` Terraform under `infra/` in INIT-104:
  out of scope; remote provisioning belongs to a remote-onboarding
  initiative once remote Flux exists (research §5.3 [E22]).
- Auto-create remote buckets via S3 SDK on first PUT: Vultr does not
  auto-create on PUT in the cited evidence (research §9.4 [E47, E48,
  E55]).
- Inherit MinIO credential keys (`MINIO_ROOT_USER`/`PASSWORD`) for
  Vultr: the Infisical handoff binds distinct provider-prefixed key
  names, and the SDK contract (D6) re-aliases them to `S3_*` at the
  consumer Secret (research §1.3 [E16]).

**Consequence**: INIT-104's surface for `vultr-vms` is documentation +
schema, not Flux manifests. When a remote channel is later onboarded,
the same channel-schema/InfisicalSecret pattern lands without
re-shaping INIT-104.

---

### D9 — D-LOCAL-CONTRACT

**Decision**: "Real local S3 round-trip" as a binding harness assertion
means **all** of the following conditions hold simultaneously, executed
by `infra/tests/validate_object_storage_local.sh` invoked from
`infra/tests/validate_platform_bootstrap.sh --cluster`:

1. `Namespace/minio-system` exists.
2. The MinIO workload Pod in `minio-system` is `Ready`.
3. `Service/minio` in `minio-system` exposes port `9000` (ClusterIP).
4. `InfisicalSecret/minio-root` (or the canonical name chosen in the
   proposal) is `Ready` and `Secret/minio-root` exists in `minio-system`
   with `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` keys non-empty.
5. The bucket Job (D3) has reached `Complete`.
6. The canonical sample bucket `humility-local-sample` exists, verified
   by an in-cluster `mc ls` against the MinIO Service.
7. A PUT of a small known-content object (e.g., `health.txt` containing
   a fixed UTF-8 string) succeeds.
8. A GET of the same object returns byte-identical content.
9. A DELETE of the object succeeds and a follow-up GET returns the
   expected 404-class error.
10. Re-running the harness is idempotent: bucket creation, object
    PUT/GET/DELETE, and Secret existence remain consistent on the
    second invocation.

The PUT/GET/DELETE step uses `mc` from a one-shot
`Job`/`kubectl run` inside the cluster (no host network exposure
required), authenticated by `Secret/minio-root`. The harness does not
expose MinIO outside the cluster.

**Evidence**: research §7.1 (real local proof: Pod Ready, ClusterIP
endpoint, credentials via Infisical-synced Secret) [E4, E11, E16, E17,
E19, E20, E25, E29, E30, E43], §7.2 (sample bucket; explicit creation
via `mc mb`/Boto3/AdminJob; PUT + GET with content verification, not
just HTTP success) [E4, E11, E43, E44, E45, E48, E55, E56, E57], §7.3
(harness extends existing local-cluster path; distinguishes missing
`mc` from missing `aws`) [E20, E44, E57, E58], §1.1 (D8 done state
requires real component reconciled by Flux into the local channel)
[E2, E4, E8, E11].

**Alternatives rejected**:
- HTTP-200 only on PUT/GET: doesn't prove byte fidelity (research §7.2
  [E48, E55]).
- Boto3 round-trip from the host: forces an SDK install on the host
  toolchain that INIT-104 has otherwise avoided; `mc`-in-cluster keeps
  the proof tooling co-located with the data plane (research §7.3
  [E20, E44, E58]).
- Skip DELETE: leaves the bucket dirty across re-runs and weakens the
  idempotency assertion (research §7.2 [E48]).

**Consequence**: The harness gains a new script and one or two
in-cluster Jobs (or `kubectl run` invocations). Bucket creation is in
the data path (D3); the harness only verifies it, plus runs the
PUT/GET/DELETE proof. The harness emits exit code 0 only when **all**
ten conditions pass.

---

### D10 — D-INIT-105-HANDOFF

**Decision**: INIT-104 does **not** depend on INIT-105 (cert-manager /
DNS / TLS). The local MinIO endpoint is plain `http://` over a
`ClusterIP` Service — no TLS, no DNS rewrite, no Ingress. The remote
`vultr-vms` endpoint is HTTPS, but Vultr Object Storage terminates TLS
at the provider; no in-cluster TLS asset is required to reach it. The
single forward-looking note carried into INIT-105 is: **if a remote
Infisical instance is later self-hosted on a `vultr-vms` channel and
served behind Ingress + TLS, the storage `InfisicalSecret`'s `server_url`
inherits whatever scheme/host that remote Infisical exposes** — which is
INIT-103's `infisical.server_url` field (already in the channel schema),
not anything INIT-104 owns.

**Evidence**: research §2.4 (local API on ClusterIP `:9000`,
plain HTTP) [E16, E43], §3.3 (Vultr requires HTTPS but terminates TLS
provider-side) [E47, E50], §5.3 (remote channel GitOps/Infisical install
is currently omitted) [E22], §1.1 (D8 environment-agnostic stack notes
that remote Infisical is the remote channel's concern) [E2, E3, E5, E9].

**Alternatives rejected**:
- Make INIT-104 depend on INIT-105 for in-cluster TLS to MinIO: not
  required for any consumer; ClusterIP traffic stays in-cluster
  (research §2.4 [E43]).
- Pre-emptively wire `https://` to MinIO via cert-manager: out of
  scope; an ingress/TLS initiative may add it later without re-shaping
  INIT-104.

**Consequence**: INIT-104 ships and merges before INIT-105.

---

### D11 — D-ANTI-SCOPE (binding)

**Decision**: The following are explicitly **not** done by INIT-104:

- cert-manager, step-ca, ACME, TLS issuers (INIT-105).
- DNS automation, ExternalDNS, CoreDNS rewrites (INIT-105).
- Ingress, public exposure, MinIO Console exposure, Pomerium routes.
- Crossplane, app-cluster fleet provisioning (INIT-017 / equivalent).
- Application workloads (`api`, `discord`) and their S3 wrappers
  (INIT-111 / INIT-112 / INIT-113).
- Authentik, OPAL/Cedar policy, tenant isolation (INIT-115).
- Backup/restore against MinIO and Vultr OS (INIT-112).
- Observability (Prometheus, Grafana, Loki, Alertmanager, OpenTelemetry)
  (INIT-117).
- CI/CD, Buildkite agent integration (INIT-110 / INIT-114).
- Container registry decisions (INIT-108).
- Remote-channel Flux install, remote `InfisicalSecret` reconciliation,
  remote MinIO/Vultr OS subscription provisioning, remote bucket
  provisioning (later remote-onboarding initiative).
- Application-scoped least-privilege S3 access keys; rotation; bucket
  policies (INIT-115).
- Schema bump to `schema_version: 2`.
- Helm controller, `HelmRelease`, MinIO Operator/Tenant CRDs, AdminJob,
  community MinIO chart (D1, D3).
- Public Console / public API exposure of MinIO (D2).
- Application Secrets in application namespaces (D6).

**Evidence**: research §1.1 (D8 says local-as-first-deployment with
real components; remote and other initiatives are scoped separately)
[E8, E10, E11], §1.4 (`infra/README.md` lists object storage and
MinIO as INIT-104/112 anti-scope so far) [E20], §5.3, §6.3 (remote
GitOps/Infisical/object_storage are outside INIT-104) [E10, E21, E22],
§9 risks and Appendix B Non-Solution Boundary [E20, E25, E16, E17,
E19, E32, E33, E34, E46, E47].

**Consequence**: The proposal phase rejects scope additions that
match this list. Any reviewer comment requesting one of the above
items is redirected to the owning INIT.

---

### D12 — D-VERSION-PINS

**Decision**: INIT-104 pins the following versions, idempotently
installed and version-checked by `infra/scripts/install-cluster-tools.sh`
and referenced from rendered manifests:

- **MinIO server image**:
  `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z`. The `quay.io/minio`
  registry path matches the chart values reference, but no chart is
  used. The exact `RELEASE.<timestamp>` tag is selected at proposal
  time as the most recent stable upstream release on or before the
  worktree's research date (`2026-04-26`); the decision binds the
  registry and the use of a `RELEASE.<timestamp>` pinned tag, not a
  floating `:latest`.
- **MinIO `mc` image** (for the in-cluster bucket Job): same
  `RELEASE.<timestamp>` family, image `quay.io/minio/mc`.
- **Host `mc` CLI**: same `RELEASE.<timestamp>` family as the image,
  installed by `install-cluster-tools.sh` at a pinned version (e.g.,
  via the `mc` binary download URL by release tag); `sha256` recorded
  alongside the binary URL, matching the existing toolchain pinning
  pattern.
- **AWS CLI**: documented as optional host tooling, not pinned. Already
  present at `aws-cli/2.34.6` per research §8.1 [E58]. The harness uses
  `mc` (in-cluster) as the canonical client (D9), not the host AWS CLI.

The proposal phase locks the exact `RELEASE.<timestamp>` strings and
SHAs.

**Evidence**: research §2.3 (chart values reference `quay.io/minio/minio`
and `quay.io/minio/mc` with `RELEASE.<date>`-style tags; project pins
versions in scripts and rendered YAML rather than floating) [E13, E31,
E41, E43], §8.1 (existing toolchain pinning pattern in
`install-cluster-tools.sh`) [E31, E59], §8.2 (`mc` missing from PATH on
2026-04-26; AWS CLI present at `aws-cli/2.34.6`) [E31, E44, E57, E58].

**Alternatives rejected**:
- Floating `:latest`: contradicts existing pinning pattern (research
  §8.1 [E13, E31]).
- Pin `mc` only as image, leaving host without `mc`: harness is
  in-cluster (D9), so a host `mc` is technically optional; nonetheless,
  pinning the host `mc` keeps the local development experience parallel
  to the in-cluster client and supports manual debugging (research
  §7.3, §8.2 [E20, E44, E57, E58]).
- Pin AWS CLI as a hard install dep: redundant with `mc`; AWS CLI is
  already present and remains optional (research §8.2 [E57, E58]).

**Consequence**: `infra/scripts/install-cluster-tools.sh` gains an
idempotent install block for `mc` matching the pattern used by the
INIT-103 entries for Helm and Infisical CLI. The MinIO and `mc` image
references in committed manifests are exact `RELEASE.<timestamp>` tags
plus image SHA digests where the upstream registry exposes them.

---

## Anti-scope (binding)

The full anti-scope list is bound by **D11**. In summary, INIT-104 does
not ship: cert-manager, DNS automation, Ingress/public exposure,
Crossplane, application workloads, Authentik / access policy,
backup/restore, observability, CI/CD, container registry decisions,
remote-channel Flux/Infisical/MinIO/Vultr OS provisioning, application
S3 wrappers, application-scoped S3 access keys, MinIO Operator/Tenant,
helm-controller / `HelmRelease`, schema bump to v2, or MinIO Console
exposure.

## Open questions (to resolve in proposal phase)

These items are research-blocked or design-decision-grade open and must
be settled in the proposal, not later:

- **OPEN-01 — Workload kind**: `Deployment` vs `StatefulSet` for the
  single-node MinIO Pod, and the implied PVC binding semantics under
  reschedule/upgrade. Research §2.2–§2.3 supports either; the choice
  drives PVC, probe, and rollout shape.
- **OPEN-02 — Local PVC size and resource requests**: The community
  chart defaults (16Gi memory, 500Gi PVC) are oversized for k3d; the
  toy setup documents 512Mi memory; INIT-104 must pin a project-specific
  number (research §2.3 [E21, E42, E43]).
- **OPEN-03 — Bucket Job lifecycle**: a one-shot Kubernetes `Job`
  (re-create on Flux re-apply via `Job`-name churn or `force: true`) vs
  a Job re-applied on each reconcile under `--ignore-existing`. Both
  are idempotent; pick one explicitly (research §2.5, §10.3 [E43,
  E44]).
- **OPEN-04 — `kubectl wait` vs probe-driven readiness**: The bucket
  Job needs MinIO ready before `mc mb`; choose between an init-container
  netcat wait, an `mc ready` probe, or an explicit
  `kubectl wait pod --for=condition=ready` orchestration step in the
  bring-up script (research §2.5, §7.2 [E43, E44]).
- **OPEN-05 — Sample bucket name**: bind exactly `humility-local-sample`
  vs a channel-derived name like `<channel>-sample` (research §4.2,
  §7.2 [E4, E11, E44]); the resolved name appears in `object_storage.bucket`
  in `infra/channels/local.yaml`.
- **OPEN-06 — Local region literal**: `us-east-1` (Boto3 default
  expectation), `local`, or an explicit channel-defined value (research
  §9.4 [E44, E50, E56]).
- **OPEN-07 — `dev` channel `object_storage` block**: ship an
  aspirational block now (no reconciler, but documents intent) vs leave
  absent until remote GitOps lands (research §6.3 [E22]).
- **OPEN-08 — Bootstrap script idempotency for credential rotation**:
  on subsequent runs, does `bootstrap-infisical-storage.sh` ever
  rotate `MINIO_ROOT_PASSWORD`? Default is no; rotation is INIT-115's
  problem (research §9.4 [E16]).
- **OPEN-09 — Application Secret materialisation**: INIT-104 does not
  create application-namespace Secrets, but the proposal phase should
  state explicitly which downstream INIT (INIT-111 vs INIT-115) owns
  the application-facing `Secret/s3-credentials` template (research
  §4.4 [E35, E36, E37]).
- **OPEN-10 — Round-trip client placement**: a one-shot `Job` vs
  `kubectl run --rm` for the harness round-trip (research §7.2, §7.3
  [E20, E44, E57, E58]); both work, choose for readability of harness
  logs.
