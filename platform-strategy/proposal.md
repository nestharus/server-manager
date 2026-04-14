# Platform Proposal

This document defines the steady-state platform design for Humility. It is
the system design for how the platform is structured, operated, and governed.
It is not a roadmap, migration plan, or reconstruction of the earlier research
history.

## Design Commitments

- The platform is designed for one operator. Any component that needs routine
  babysitting, duplicate control planes, or constant tuning is wrong-sized.
- The platform exists to serve `services/api`, `services/discord`, and
  `apps/web`. Shared services are adopted only when they directly reduce risk
  or recurring operator work for those three surfaces.
- The platform is Vultr-centric and Cloudflare-fronted. Managed services are
  preferred when they reduce operator attention and still expose standard
  interfaces. Vultr is not the cheapest raw compute host, but it is the best
  fit for the intended shape: managed Kubernetes control planes, managed
  PostgreSQL, object storage, and standard infrastructure interfaces from one
  provider without Railway's narrower service-centric model or Hetzner's
  account-limit and self-managed-substrate burden.
- Kubernetes is for stateless application runtime and declarative control.
  Durable state lives outside Kubernetes in managed services.
- Git is the approval ledger. OpenTofu bootstraps external prerequisites, Flux
  reconciles desired state from Git, and Crossplane provisions environment
  infrastructure from claims.
- `dev` and `production` are persistent environments. `staging` is an
  on-demand release-candidate environment with explicit creation and teardown.
- Clusters are rebuildable from Git and bootstrap state. Databases, buckets,
  identities, secrets, and historical records are lived state and are governed
  by backup and recovery workflows rather than by rebuild assumptions.
- Railway remains a credible speed-to-MVP option for a smaller
  `api + daemon + db` system, but it is not the steady-state substrate for
  Humility's explicit environment boundaries, GitOps control plane, and
  cluster-scoped runtime services.
- Hetzner and Contabo are rejected as the primary steady-state substrate even
  though they are cheaper on raw compute. Hetzner's documented account-limit
  friction and Contabo's VPS-first operational shape move too much burden back
  onto a single operator.

## Platform Topology

### Steady-State Shape

The steady-state platform has one always-on platform cluster and one
application cluster per persistent environment:

- `platform` VKE cluster: shared control plane and shared operator services
- `dev` VKE application cluster: persistent, lower-cost environment for active
  development, E2E, and UI validation
- `production` VKE application cluster: persistent, promotion-only environment
- `staging` VKE application cluster: created only for a specific release
  candidate, then destroyed

The application clusters host product workloads only:

- `services/api`
- `services/discord`
- `apps/web`
- environment-local workers such as OCR or background job consumers

The platform cluster does not host product traffic. It hosts the control and
operator surfaces that all environments share.

### External Managed Services

| Component | Placement | Purpose |
|---|---|---|
| OpenTofu bootstrap state | Outside Kubernetes | Creates the external prerequisites that must exist before clusters can reconcile themselves |
| Cloudflare DNS and edge | Managed outside clusters | Public DNS, TLS, and edge protection |
| Vultr Managed PostgreSQL | Managed outside clusters, per environment | Durable relational state for persistent and temporary environments |
| Vultr Object Storage | Managed outside clusters, environment-separated buckets | Media uploads, OCR source images, backup exports, and retained artifacts |
| Managed OCI registry | Managed outside clusters, shared | Stores immutable application images and OCI-packaged release artifacts; `GHCR` is the default unless a provider-native registry earns the extra coupling trade |
| External uptime probe | Managed outside clusters | Keeps production API visibility even if the platform cluster is impaired |

### Platform Cluster Services

The platform cluster is intentionally narrow. It hosts:

- Flux controllers for platform reconciliation
- Crossplane and provider controllers for environment provisioning
- Shared observability:
  - Prometheus
  - Alertmanager
  - Grafana
  - Loki
  - blackbox exporter
- Secret and operator access services:
  - Infisical for secret distribution and scoping
  - Authentik as the shared operator identity provider and OIDC broker
  - Pomerium as the operator-only access gateway for protected dashboards,
    internal services, and SSH/TCP access
  - Smallstep as the deliberate internal PKI authority for workload identity,
    cert-manager integration, and SSH/X.509 issuance beyond what Pomerium and
    Infisical already cover
- Shared policy distribution only where the product needs centralized policy
  fan-out:
  - OPAL on the platform cluster distributes policy and policy data
  - Cedar evaluation stays local to the API path in application clusters

The platform cluster does not host:

- shared application ingress for product traffic
- environment-specific product workloads
- self-hosted Postgres
- self-hosted object storage
- per-environment dedicated monitoring estates
- Elasticsearch-based logging clusters

### Application Cluster Services

Each application cluster hosts:

- one ingress controller for that environment
- `services/api`
- `apps/web`
- `services/discord`
- background workers and environment-local schedulers
- app-local Cedar authorization evaluation for `services/api`
- lightweight metrics exporters and log shippers

`services/discord` is deployed in the application cluster but is outbound only.
It does not receive public ingress.

### Resource Assumptions

These are design assumptions for a serious but proportionate baseline. Current
vendor pricing and exact SKUs must be revalidated at implementation time.

| Cluster | Baseline shape | Notes |
|---|---|---|
| `platform` | one node pool, `2 x 2 vCPU / 8 GB` | Enough for GitOps, Crossplane, secrets, and shared observability |
| `dev` | one node pool, `2 x 2 vCPU / 4 GB` | Lower cost and lower urgency than production |
| `production` | `system` pool `2 x 2 vCPU / 4 GB`, `general` pool `2 x 4 vCPU / 8 GB` | Separate system and workload placement with enough headroom for API, web, daemon, and workers |
| `staging` | same topology as production, created on demand | Production-like by default because it exists for release-candidate benchmarking, load validation, and exact-candidate smoke |

The platform assumes a single Vultr region until a concrete latency or
compliance requirement justifies multi-region cost and complexity.

### Network and Edge Boundaries

- Each application cluster gets its own ingress controller and its own public
  load balancer.
- Cloudflare is the only public DNS and edge entrypoint. `production` receives
  the strongest edge policy. `dev` can use lighter protection. `staging`
  receives temporary DNS only for the lifetime of the release candidate.
- The platform cluster does not terminate product traffic.
- Environment boundaries are network boundaries, not just namespace
  boundaries. Private networking, managed database access, and bucket access
  are scoped per environment.
- Backups cross the runtime boundary intentionally: production databases and
  retained blobs are exported to object storage so recovery does not depend on
  the survival of a single cluster or a single managed service instance.

## Environment Contracts

| Environment | Lifetime | Runtime contract | Data contract | Operational contract |
|---|---|---|---|---|
| `dev` | Persistent | Dedicated cluster, lower-cost shape, allowed to be noisier | Dedicated dev Postgres and dev buckets with current schema, release/reference seeds, and synthetic test fixtures | Used for active development, E2E, and iterative UI/video validation; shared monitoring, lower urgency alerts |
| `staging` | On demand | Temporary cluster created from a prod-like template for one explicit release candidate | Temporary Postgres and buckets created from schema plus release/reference seeds and synthetic or masked benchmark data as needed | Used only for release-candidate validation, benchmarking, and load/performance checks; no standing spend, no persistent alert channel |
| `production` | Persistent | Dedicated cluster, promotion-only, most conservative rollout rules | Dedicated managed Postgres and production buckets with full backup and restore policy | Real operator alerts, strongest access controls, explicit promotion gate |

Environments are not copies. They are different promises about persistence,
validation fidelity, failure tolerance, and cleanup.

Short-lived validation or recovery environments are allowed through ordinary
`EnvironmentClaim` mechanics, but they are not a fourth standing environment.
They are non-promotable, TTL-bound claims used for restore drills,
infrastructure validation, or other one-off checks that need real provisioning.

## Control Objects

The platform is governed by a small set of explicit control objects.

| Object | Owner | Required fields | Purpose |
|---|---|---|---|
| `EnvironmentClass` | Git + Flux | `name`, `persistence`, `haProfile`, `sharedPlatformServices`, `dedicatedServices`, `ingressPolicy`, `ttlAllowed`, `approvalPolicy`, `destroyPolicy` | Defines the contract for `dev`, `staging`, and `production` |
| `EnvironmentClaim` | Git + Flux, reconciled by Crossplane | `name`, `classRef`, `owner`, `releaseRef`, `clusterProfile`, `secretsProfile`, `dnsPrefix`, `expiresAt`, `dataPolicy`, `status` | Requests a real environment and its environment-scoped infrastructure |
| `PlatformService` | Git + Flux | `name`, `scope`, `sourceRef`, `version`, `dependsOn`, `exposure`, `approvalPolicy`, `driftPolicy` | Declares a shared platform capability reconciled in the platform cluster |
| `ReleaseRef` | CI output, pinned in Git | `appVersion`, `imageDigests`, `deployBundleVersion`, `schemaVersion`, `seedVersion`, `scanStatus` | Names the immutable release being promoted and deployed |
| `Promotion` | Git + Flux | `name`, `fromEnvironment`, `toEnvironment`, `releaseRef`, `requiresStaging`, `stagingClaimName`, `stagingExpiresAt`, `approvalState`, `executedAt`, `status` | Defines the only legal path for moving a release between environments |

### Object State Expectations

- `EnvironmentClaim.status` moves through:
  - `Requested`
  - `Provisioning`
  - `Ready`
  - `Expiring`
  - `Destroying`
  - `Deleted`
  - `Failed`
- `Promotion.status` moves through:
  - `Draft`
  - `StagingProvisioning`
  - `StagingReady`
  - `Validated`
  - `ProductionApproved`
  - `Promoted`
  - `Rejected`
  - `Expired`

`production` is never updated by "latest". A `Promotion` must reference an
explicit `ReleaseRef`, and that `ReleaseRef` must name immutable image digests
and an explicit schema version.

## Ownership Boundaries

### OpenTofu

OpenTofu owns only bootstrap and account-level prerequisites:

- platform cluster creation
- base networking primitives
- provider credentials and bootstrap identities required to let GitOps run
- shared managed resources that must exist before Crossplane can manage the
  rest of the platform

OpenTofu does not own:

- application cluster lifecycle after bootstrap
- application deployment
- release promotion
- day-2 environment churn

### Flux

Flux owns Git-to-cluster reconciliation:

- platform cluster manifests
- Crossplane installation and package updates
- shared platform services
- environment cluster bootstrap and application deployment
- release pin application from `ReleaseRef`

Flux is the source of reconciliation truth for Kubernetes resources, not for
lived data.

### Crossplane

Crossplane owns environment provisioning from claims:

- creation and deletion of downstream environment clusters
- creation of environment-scoped managed Postgres, buckets, and other runtime
  dependencies that are part of the environment contract
- application of environment-class differences such as shared versus dedicated
  platform services

Crossplane provisions environments. It is not a second release system.

### Buildkite

Buildkite owns CI graph execution only:

- build, test, and scan application artifacts
- publish immutable images and release bundles
- produce the `ReleaseRef` metadata or the Git change that updates a pinned
  release reference

Buildkite does not own:

- steady-state cluster reconciliation
- imperative cluster deployment as the primary path
- a custom environment event backbone
- database migrations outside the approved release flow

Buildkite prepares approved release inputs. Flux and Crossplane reconcile the
running system from Git.

## Data and Runtime Design

### Relational State

The system of record is managed PostgreSQL:

- `production`: dedicated managed Postgres cluster on a PITR-capable tier
- `dev`: dedicated smaller managed Postgres cluster
- `staging`: on-demand managed Postgres environment created only for release
  validation

Atlas is the schema authority. SQLAlchemy Core is the default data-access
layer. `asyncpg` is reserved for explicitly justified Postgres-heavy or
performance-critical paths behind repository boundaries. The platform assumes
standard Postgres features only, so migration away from Vultr remains painful
but possible without compatibility shims.

The proposal explicitly rejects Kubernetes-hosted Postgres for the initial
platform. `production` must not use a no-recovery managed tier. If
self-hosting ever becomes unavoidable, a single VM is acceptable only for
`dev` or short bootstrap phases, not as the production steady-state answer.

### Typed Query and Mutation Model

The platform keeps schema authority, runtime queries, and API contracts
separate:

- Atlas owns schema evolution and `schemaVersion`
- SQLAlchemy Core owns the default repository/query path
- typed API contracts remain explicit at the service boundary and are suitable
  for OpenAPI-driven shared types
- query-specific read models and projections are preferred over generic ORM
  entity hydration

Humility does not treat ORM models as the public contract. The platform favors
explicit DTOs, query-specific projections, and generated/shared contract types
over implicit runtime model sharing between the API, web app, and agent-facing
surfaces.

For mutable current-state entities, the platform-level concurrency and audit
convention is activity-based rather than row-version-based:

- business tables hold current state needed for normal reads and writes
- append-only activity records capture actions, resulting state changes, actor
  identity, timestamps, and canonical change hashes
- API callers update mutable resources with an `ETag`-style concurrency token
  derived from the latest activity head, not from an integer row version
- stale writes fail as conflicts at the API boundary
- read-optimized head/projection tables are allowed where they keep the latest
  state or latest activity hash cheap to query

The proposal does not fix the exact application-level action/state-change
schema. It fixes the platform stance: auditing, optimistic concurrency, and
history should converge on one activity model instead of mixing row version
columns, ad hoc audit tables, and disconnected logs.

### Seeds and Reference Data

`ReleaseRef.seedVersion` identifies immutable release/reference seed data used
to construct disposable or non-production environments. These seeds are:

- not backups
- not replicas of live user history
- not substitutes for production recovery

Default non-production data policy:

- schema from Atlas migrations
- release/reference seed SQL
- synthetic test fixtures

Masked benchmark datasets are allowed only for explicit release validation
needs. Raw production clones are not part of the normal staging model.

### Object Storage

Object storage is provider-managed and environment-separated:

- `prod-media`
- `prod-backups`
- `dev-media`
- `dev-backups`
- temporary staging buckets per release candidate

Object storage is for blobs, media, and backup exports. It is not used as a
fake artifact registry.

### Validation and Test Strategy

The validation stack is layered and environment-specific:

- Buildkite runs lint, unit, contract, integration, and artifact/supply-chain
  checks on every candidate release
- database integration tests use `testcontainers-python`, Atlas migrations,
  base SQL reference seeds, and scenario overlay SQL rather than long-lived
  shared test databases
- `dev` is the main E2E and iterative validation surface, including UI/video
  QA and ordinary cross-surface smoke for `services/api`, `services/discord`,
  and `apps/web`
- `staging` exists only for exact-candidate validation that needs prod-like
  isolation: benchmark runs, load/performance tests, and release-candidate
  smoke on the real deployment topology
- `production` gets only post-promotion smoke and live monitoring, not
  exploratory QA or benchmark traffic

This keeps frequent validation cheap and fast in `dev` while reserving
`staging` for the narrow checks that actually need a separate prod-like
runtime.

### Release Artifacts

Every deployable release produces:

- OCI image digests for each workload
- a versioned deployment bundle for Flux
- an Atlas schema version
- a seed-data version
- an SBOM and image signature/provenance record
- vulnerability scan results

The platform requires a real OCI-capable artifact store and digest-pinned
deploys. It does not require a self-hosted all-in-one artifact platform on day
one. A managed registry is the baseline because it buys operator time; a
self-hosted registry only becomes justified when the existing registry blocks
release workflows on concrete grounds. Object storage is not the release API,
and mutable registry tags are not the deployment truth.

Baseline supply-chain controls are:

- Trivy in CI for repository, image, and IaC scanning
- SBOM generation and Cosign-style artifact signing
- one dependency updater bot, with Renovate preferred over heavier custom
  update machinery

## Operational Workflows

### 1. Bootstrap and Platform Reconciliation

1. A human applies OpenTofu against the bootstrap configuration.
2. OpenTofu creates the platform cluster and the prerequisites required for
   Flux and Crossplane to run.
3. Platform Flux reconciles shared services, Crossplane packages, and control
   objects from Git.
4. Crossplane becomes able to reconcile environment claims.
5. Persistent environment claims for `dev` and `production` are reconciled into
   real clusters and managed runtime dependencies.

This workflow ends when Git owns desired state and the platform can recreate
non-production environments from claims.

### 2. Persistent Environment Lifecycle

1. A Git change creates or updates a persistent `EnvironmentClaim`.
2. Flux applies the claim to the platform cluster.
3. Crossplane provisions or updates the target environment cluster and its
   managed runtime dependencies.
4. Environment-local Flux deploys the application release referenced by
   `releaseRef`.
5. The environment reaches `Ready` only after health checks, deployment status,
   and baseline telemetry succeed.

Persistent environments are not created from ad hoc console steps.

### 3. Promotion Workflow

1. Buildkite builds immutable artifacts, runs baseline Trivy scanning, signs
   release artifacts, and produces a `ReleaseRef` or the Git change that pins
   that release reference.
2. `dev` advances by updating the `dev` release pin after successful build and
   verification.
3. A human creates or merges a `Promotion` from `dev` to `staging` using the
   exact `ReleaseRef`.
4. That promotion creates a temporary staging `EnvironmentClaim`.
5. Crossplane provisions staging, Flux deploys the exact candidate, and the
   system validates release behavior against the staging contract.
6. A human creates or merges a `Promotion` from `staging` to `production`
   using the same `ReleaseRef`.
7. Flux deploys production from the pinned release. No rebuild or mutable-tag
   retargeting occurs during promotion.

Only one production-targeting `Promotion` may be active at a time.

### 4. Staging Creation and Teardown

`staging` exists only to validate a specific release candidate.

Creation:

1. A `Promotion` or explicit short-lived `EnvironmentClaim` is merged.
2. Crossplane provisions a staging cluster and staging-scoped managed data
   resources.
3. Flux deploys the referenced release and runs the validation stack.

Teardown:

1. The claim is deleted manually or expires by TTL.
2. Crossplane destroys the staging cluster and staging-scoped runtime
   dependencies.
3. Logs, artifacts, and backups follow their own retention rules and are not
   implicitly deleted with the cluster.

### 5. Database Migration and Recovery

1. Atlas migrations are built and versioned as part of the release.
2. Non-production environments apply migrations before or during deploy under
   the same release pin used by the application workloads.
3. Production migrations run only under an approved production promotion.
4. Production uses managed backups plus scheduled encrypted logical backups
   exported to object storage.
5. Restore drills occur into an isolated recovery environment and must verify:
   - database restore success
   - application startup
   - a minimal read/write smoke path

Git recreates clusters. Backups and runbooks recover stateful data.

### 6. Monitoring and Incident Response

The observability design is intentionally narrow:

- shared Prometheus, Alertmanager, Grafana, Loki, and blackbox exporter on the
  platform cluster
- one external production API probe outside the platform cluster
- structured JSON logs with request, job, and release correlation IDs
- Trivy scanning in CI and promotion gates

Loki stays in a deliberately small, short-retention shape. Logs are for
diagnosis after a metric or external probe fires, not as the primary paging
surface.

The platform monitors only failure modes with a named operator action:

| Surface | Primary signals | Expected operator action |
|---|---|---|
| Production API | external probe, latency, 5xx rate | inspect ingress and app logs, compare to last release, rollback if release-caused |
| Discord daemon | gateway connectivity, reconnect loops, event-loop lag | restart deployment, inspect downstream API reachability |
| Database | connectivity, pool saturation, backup age, restore-test age | recover service, halt unsafe writes, restore if needed |
| OCR workers | queue age, retry count, provider failures | drain or pause workers, fall back to manual review if necessary |
| GitOps | failed reconcile, stuck rollout, suspended resources | revert bad commit or fix manifest, then reconcile |
| Vulnerability scanning | new fixable `CRITICAL` or `HIGH` prod-bound findings | block promotion until fixed or explicitly waived |

Paging alerts must not be derived solely from logs and must include a first
operator action. AI-assisted triage may be added later as an operator-in-the-
loop diagnostic aid, but it is not part of the baseline detection path.

The proposal explicitly excludes:

- distributed tracing
- per-environment persistent observability stacks
- Elasticsearch-based logging
- synthetic browser monitoring suites
- autonomous or always-on AIOps layers
- dashboards with no linked operator action

### Spend Tracking

Spend tracking is intentionally simple:

- Vultr billing history and invoice exports are the infrastructure spend source
  of truth
- Google Cloud budgets and alerts govern Vision/Gemini usage-based spend
- monthly operator review groups spend into persistent baseline, temporary
  staging spend, and usage-based OCR/LLM spend

The proposal explicitly does not adopt OpenCost or another always-on chargeback
tool in the baseline. At this scale, lifecycle control and budget alerts are
more valuable than a self-hosted FinOps surface.

## Governance

### Approval Rules

Human approval is required for:

- any OpenTofu apply or destroy
- changes to OpenTofu bootstrap configuration
- changes to Crossplane providers, XRDs, or compositions
- adding or removing shared platform services
- creating or deleting persistent environments
- any production promotion
- any production DNS, ingress, WAF, or secret-scope change
- destructive data operations, including irreversible schema changes,
  restore-cutover steps, and deletion of retained records

Automation is allowed for:

- Flux reconciliation of already-approved Git changes
- Crossplane provisioning or deletion of non-production environments from
  approved claims
- `dev` release advancement after CI succeeds
- TTL-based staging teardown
- ordinary drift correction for Kubernetes resources owned by Flux

### Drift Model

Drift is treated as a normal operating condition at three layers:

- OpenTofu drift in provider-level resources
- Flux drift in Kubernetes objects
- lived-state drift in databases, buckets, identities, and emergency console
  actions

The handling rules are different:

- Flux auto-corrects resources it owns unless reconciliation is intentionally
  suspended.
- Crossplane auto-corrects infrastructure drift it owns, but never treats
  stateful data as safely recreatable by default.
- OpenTofu drift is detected by planned runs and corrected deliberately by a
  human. OpenTofu is never auto-applied from CI.
- Emergency manual changes are allowed, but they must either be backfilled into
  Git the same day or recorded as explicit temporary drift with a recovery
  note.

### Identity, Access, and Secrets

The platform separates operator access from product runtime access:

- Cloudflare is the public edge for DNS, TLS, WAF, rate limiting, and origin
  protection for product-facing traffic.
- Authentik authenticates human operators and brokers shared OIDC identity for
  internal platform surfaces.
- Pomerium mediates access to dashboards, operator APIs, and cluster-adjacent
  internal services, including privileged SSH/TCP access.
- Smallstep is the distinct internal PKI authority for automation, workload
  identity, and service certificates beyond what Pomerium and Infisical
  already cover, and its scope stays explicit so it does not become a
  duplicate access or secrets layer.
- Infisical stores environment-scoped secrets and distributes them to clusters
  and workloads, with machine-auth flows anchored there rather than in the
  application runtime.
- Cedar is the application authorization engine in the API path. OPAL is added
  only when Humility needs shared live distribution of authorization policy or
  policy data across environments.
- PostgreSQL RLS, if used later, is driven by JWT claims and database policy;
  it is not a Logto-specific platform feature and does not keep Logto in scope.

These services are shared platform capabilities. They are not replicated per
environment unless a real boundary requires it.

## Cost Posture

The platform must remain proportionate to a community of roughly Humility's
current size. The proposal assumes the following order-of-magnitude monthly
envelopes, using current vendor pricing as a sanity check rather than as a
locked purchasing commitment:

| Envelope | Monthly range | Assumptions |
|---|---:|---|
| Low | `$150-$225` | minimal shared control plane, one persistent runtime, smallest serious managed data footprint |
| Base steady state | `$220-$360` | persistent `platform`, `dev`, and `production`, managed Postgres, shared observability, managed registry, object storage |
| Stress month | `$320-$520` | on-demand `staging`, larger worker footprint, temporary validation databases, benchmark windows, and higher retained artifacts |

The main cost drivers are:

- persistent worker nodes
- managed PostgreSQL
- public load balancers
- retained backups
- observability headroom on the platform cluster

Object storage, registry fees, and baseline DNS are smaller contributors at
Humility's scale.

The biggest cost-control lever that does not violate the philosophy is keeping
`staging` on demand. The platform explicitly pays for managed Kubernetes and
managed Postgres because those purchases buy operator time. The proposal does
not assume a full per-environment platform estate, a self-hosted database
fleet, or a self-hosted artifact platform in the baseline cost.

Current provider prices must be revalidated before implementation or
re-pricing. The proposal relies on the shape of the spend, not on a frozen
price sheet.

## Constraints

- One operator remains the design point.
- The platform assumes a live Discord-facing product with durable records and
  no tolerance for casual data loss.
- Managed services are preferred when they reduce operator attention and do not
  force proprietary application code.
- The platform starts single-region.
- Git remains the approval ledger even when non-production convenience APIs are
  added.
- Staging is temporary by design.
- The design must work without compatibility shims or transitional dual-path
  behavior.

## Non-Goals

- Reproducing the full `base-application` enterprise platform for Humility's
  initial steady state
- Always-on staging
- Kubernetes-hosted Postgres
- Self-hosted object storage
- Elasticsearch-based logging estates
- Distributed tracing before it becomes an operational blocker
- Harbor or another self-hosted registry as a day-one stateful control plane
- Recreating the legacy Dagger + PostgreSQL + Kafka + Debezium + Redis
  orchestration backbone for CI/CD and environment sync
- S3-backed artifact registry hacks
- Full multi-cloud portability abstractions
- Treating Git as a substitute for database backups and disaster-recovery
  runbooks
- Building platform components whose only justification is future elegance

## Traceability

Axis abbreviations:

- `A1`: small-platform capability dead zone
- `A2`: environments are different contracts
- `A3`: operator simplicity versus provider independence
- `A4`: declared intent versus lived infrastructure
- `A5`: visibility versus limited attention
- `A6`: platform work competing with the product

Principle abbreviations:

- `P1`: One Operator Is the Design Point
- `P2`: The Platform Serves the Product
- `P3`: Buy Operator Time, Not Independence
- `P4`: Environments Are Contracts, Not Copies
- `P5`: Declare Intent, Respect Drift
- `P6`: Observability Within Attention Budget
- `P7`: Cost Proportionate to Community
- `P8`: Change Is Expected; Churn Is Not
- `P9`: Complexity Must Be Earned

| Mechanism | Problem axes | Philosophy principles |
|---|---|---|
| Vultr-centric managed control plane with managed Postgres and object storage | `A1`, `A3`, `A5`, `A6` | `P1`, `P2`, `P3`, `P7`, `P9` |
| One platform cluster plus one app cluster per persistent environment | `A2`, `A4`, `A6` | `P1`, `P4`, `P5`, `P9` |
| On-demand `staging` with TTL-bound claims | `A1`, `A2`, `A5`, `A6` | `P1`, `P4`, `P6`, `P7`, `P9` |
| `EnvironmentClass`, `EnvironmentClaim`, `Promotion`, and immutable `ReleaseRef` objects | `A2`, `A4`, `A6` | `P2`, `P4`, `P5`, `P8`, `P9` |
| Hard boundary between OpenTofu bootstrap, Flux reconciliation, and Crossplane provisioning | `A3`, `A4`, `A6` | `P3`, `P5`, `P8`, `P9` |
| Shared observability stack with limited alert surface | `A5`, `A6` | `P1`, `P2`, `P6`, `P7`, `P9` |
| Managed Postgres plus off-provider logical backups and restore drills | `A1`, `A3`, `A4`, `A5` | `P1`, `P3`, `P5`, `P7`, `P8` |
| Git as approval ledger with manual gates for bootstrap, persistent envs, and production | `A4`, `A5`, `A6` | `P1`, `P2`, `P5`, `P8`, `P9` |
| Shared identity, secret, and policy services on the platform cluster | `A3`, `A4`, `A5` | `P1`, `P2`, `P3`, `P5`, `P9` |
