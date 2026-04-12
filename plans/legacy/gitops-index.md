# GitOps / CI-CD Legacy Spec Decomposition

## 1. Executive summary

This legacy specification defines a CI/CD and environment-management control plane centered on Dagger-driven builds, PostgreSQL-backed state, Kafka eventing, and a hybrid environment workflow that splits dynamic environments (API-managed) from static environments (Git-managed). Its scope covers build orchestration, build-state contracts, environment-state contracts, log ingestion, timeout handling, and the synchronization path from a protected Git repository into database-backed environment records. It assumes several lower layers already exist but does not specify them fully: authenticated user tokens with team claims, an artifact store behind `artifact_url`, a final deployment system that consumes deployment-ready events, an environment provisioner that reacts to environment CDC events, a shared cache/VFS layer for Dagger, and an SCM/UX layer for PR review, source links, and Git webhooks. It is a control-plane specification, not a full runtime-platform specification: it defines how state is recorded, published, and observed, but leaves substantial infrastructure, security, deployment-runtime, and operations details to adjacent documents.

## 2. Component inventory

| Component | Role in this spec | Category | External dependency? | Notes |
|---|---|---|---|---|
| Dagger | Defines and executes CI/CD pipeline logic; source of build logs; consumer of cache strategy | CI/CD | Yes | Central build engine and orchestration substrate |
| PostgreSQL | Canonical current-state store for deployments, builds, and environments | storage | Yes | All state changes commit here before publication |
| Kafka | Durable event backbone for build, deployment, and environment workflows | messaging | Yes | Carries task, started, completed, ready, and CDC events |
| Debezium | Streams committed PostgreSQL changes from WAL into Kafka | messaging | Yes | Foundation of the spec's auditability model |
| Redis | Ephemeral accelerator for atomic deployment-success counters | storage | Yes | Not source of truth; used only for aggregation |
| Elasticsearch | Stores and queries structured build logs | observability | Yes | Backing store for debugging and traceability UI |
| Kibana | Visualizes Elasticsearch data | observability | Yes | One of two allowed UI options |
| Custom Frontend | Alternative UI over Elasticsearch data | observability | No | Expected to provide richer debugging UX than raw Kibana |
| FastAPI | Framework for the synchronous environment-management REST API | API | Yes | Named implementation framework |
| Python | Language/runtime for the FastAPI API service | other | Yes | Only explicitly named language in the document |
| Pydantic | Request/response validation layer for API contracts | API | Yes | Mandatory for all API models |
| Shared VFS | Shared cache host for highly granular Dagger cache volumes | storage | Yes | Exact product is not specified |
| Elasticsearch Ingest Pipeline | Parses and enriches raw Dagger logs before indexing | observability | No | Adds structured fields and contextual metadata |
| Orchestrator | Coordinates deployments, consumes build/env events, updates state, emits readiness | compute | No | Sometimes called Dagger Orchestrator pipeline |
| Builder Services | Ephemeral workers that execute build tasks and emit lifecycle events | compute | No | Kafka consumers for `dev.platform.build.task.v1` |
| Timeout-management Service | Stateful timer service for detecting and reporting build timeouts | compute | No | Publishes synthetic `build.completed` failures |
| environment-manager-api service | Synchronous REST API for API-managed environments | API | No | Enforces authorization and optimistic locking |
| GitOps Controller | Syncs Git-managed environment definitions into PostgreSQL | compute | No | Triggered by webhook after protected-branch updates |
| Static environments Git repository | Source of truth for long-lived Git-managed environments | CI/CD | Yes | Protected repo with PR-based change control |
| Git | Version-control mechanism for static environment definitions | CI/CD | Yes | Used for branches, merges, tags, and `git_ref` identity |
| Webhook | Trigger from Git merge activity into the GitOps controller | networking | Yes | Security model is not specified |
| Pull Request (PR) workflow | Mandatory review path for static environment changes | CI/CD | Yes | Required before protected-branch merge |
| PostgreSQL Write-Ahead Log (WAL) | Low-level change source consumed by Debezium | storage | No | Explicitly part of the eventing design |
| `deployments` table | Stores deployment-level expected build count and aggregate status | storage | No | Parent table for build records |
| `builds` table | Stores per-service build state, artifact URL, and version | storage | No | Source table for build task CDC events |
| `environments` table | Stores environment definitions and metadata | storage | No | Shared convergence point for API and Git workflows |
| `platform.builds.v1` | Kafka topic for build task/start/completion events | messaging | No | Includes both Debezium and service-produced events |
| `platform.deployments.v1` | Kafka topic for deployment readiness events | messaging | No | Carries `dev.platform.deployment.ready.v1` |
| `platform.environments.cdc.v1` | Kafka topic for immutable environment change events | messaging | No | Unified event stream for both API and Git changes |
| `/environments` REST API | CRUD surface for API-managed environments | API | No | Includes list, get-by-name, create, update, delete |
| JSON configuration files (`production.json`, etc.) | Declarative source format for Git-managed static environments | other | No | File schema is implied but never defined |
| SHA256 | Hashing algorithm for cache `content_hash` generation | security | No | Used in Dagger cache-key contract |

## 3. Architectural decisions

| ID | Decision | Rationale | Scope | Confidence | Modernization risk |
|---|---|---|---|---|---|
| AD-01 | Use Dagger as the CI/CD execution engine | Explicit: Dagger is "the engine for defining and executing all CI/CD pipeline logic" | Dagger, Builder Services, Orchestrator | HIGH | HIGH - Dagger-first CI may already be superseded in the modernization target |
| AD-02 | Execute pipeline logic inside isolated containers | Explicit: pipeline logic runs "within isolated containers" | Dagger, Builder Services | HIGH | LOW - generic pattern, but runtime details are unspecified |
| AD-03 | Use PostgreSQL as the canonical current-state store | Explicit: PostgreSQL is the "canonical source of truth for all system state" | PostgreSQL, all tables, Orchestrator, API, GitOps Controller | HIGH | LOW |
| AD-04 | Use Kafka as the central asynchronous communication backbone | Explicit: Kafka is the "central communication backbone for all asynchronous communication" | Kafka, Orchestrator, Builders, Timeout Service, API flows | HIGH | LOW |
| AD-05 | Publish state changes through Debezium CDC from the PostgreSQL WAL | Explicit: Debezium streams "all committed state changes" from WAL to Kafka | PostgreSQL WAL, Debezium, Kafka | HIGH | MEDIUM - strong vendor/tool coupling to Debezium conventions |
| AD-06 | Treat the Transactional Outbox pattern as foundational for all state changes | Explicit: it is the "foundational principle for all state changes" | PostgreSQL, Debezium, Kafka, Orchestrator, API, GitOps Controller | HIGH | LOW |
| AD-07 | Require state changes to commit atomically to PostgreSQL before events are emitted | Explicit: "All state modifications must first be committed atomically" | PostgreSQL, Debezium, Kafka | HIGH | LOW |
| AD-08 | Treat PostgreSQL as current state and Kafka as immutable audit history | Explicit: database is "source of current state" and Kafka is "immutable, auditable source of truth over time" | PostgreSQL, Kafka, downstream consumers | HIGH | LOW |
| AD-09 | Parallel CI depends on a multi-layered, highly granular, content-addressed cache strategy | Explicit: success is "contingent upon the correct implementation of this granular caching architecture" | Dagger, Shared VFS, cache key contract | HIGH | MEDIUM - highly tuned assumption may not survive engine changes |
| AD-10 | Host Dagger cache volumes on a shared VFS | Explicit: cache volumes are "hosted on a shared VFS" | Shared VFS, Dagger | HIGH | HIGH - storage backend is unnamed and may be obsolete or insufficient |
| AD-11 | Use `dagger.CacheSharingMode.LOCKED` on granular cache volumes | Explicit: exact Dagger sharing mode is prescribed | Dagger, Shared VFS | HIGH | HIGH - exact API and contention model are tool/version specific |
| AD-12 | Structure and enrich logs using `build_id` plus an Elasticsearch ingest pipeline | Explicit: logs are enriched with `build_id` and processed by an ingest pipeline | Dagger, Elasticsearch, Elasticsearch Ingest Pipeline, UI | HIGH | MEDIUM - assumes Elastic-centric observability path |
| AD-13 | Decouple timeout detection into a dedicated, stateful timeout-management service | Explicit: timeout management is a "dedicated, stateful timeout-management service" | Timeout Service, Kafka, Orchestrator | HIGH | LOW |
| AD-14 | Standardize failure signaling on `dev.platform.build.completed.v1` | Explicit: timeout service publishes the same completion event; new monitors can signal failure the same way | Kafka, Timeout Service, Builders, Orchestrator | HIGH | LOW |
| AD-15 | Support a hybrid environment model: API-managed dynamic environments plus Git-managed static environments | Explicit: two "distinct but complementary paradigms" are required | environment-manager-api, GitOps Controller, Git repository, PostgreSQL | HIGH | LOW |
| AD-16 | Converge API and Git environment workflows at the `environments` table and `platform.environments.cdc.v1` | Explicit: "both workflows converge at the database" and share the same CDC topic | PostgreSQL, Debezium, Kafka, API, GitOps Controller, Orchestrator | HIGH | LOW |
| AD-17 | Manage static environments in a protected Git repository with mandatory PR approval | Explicit: static env repo uses "protected main branch" and "mandatory PR approval" | Git repository, Git, PR workflow, Webhook | HIGH | MEDIUM - depends on SCM feature set and governance details |
| AD-18 | Implement a custom GitOps controller that reconciles Git state directly into PostgreSQL | Explicit: "A new GitOps controller service synchronizes the state from Git to the PostgreSQL database" | GitOps Controller, Git repository, PostgreSQL | HIGH | HIGH - custom controller may duplicate broader GitOps tooling |
| AD-19 | Mark Git-managed environment records as system-owned and platform-owned | Explicit: Git-managed rows use `"system"` plus the platform team ID; API contract also assumes `management_type = 'GIT'` | GitOps Controller, `environments` table, API auth logic | HIGH | HIGH - field names are internally inconsistent and partially absent from schema |
| AD-20 | Register deployment and build rows in one database transaction at deployment start | Explicit: Orchestrator writes both records "in a single database transaction" | Orchestrator, PostgreSQL, `deployments`, `builds` | HIGH | LOW |
| AD-21 | Use ephemeral builder services that consume tasks and emit started/completed events | Explicit: "Ephemeral Builder services consume" tasks and publish lifecycle events | Builder Services, Kafka, Dagger | HIGH | LOW |
| AD-22 | Aggregate successful builds with a Redis counter and publish readiness only when the count reaches `expected_build_count` | Explicit in flow and workflow sections | Redis, Orchestrator, Kafka, `deployments`, `builds` | HIGH | MEDIUM - no recovery semantics if Redis state is lost |
| AD-23 | Represent build tasks as Debezium envelopes over full `builds` rows | Explicit: payload is "a Debezium change event envelope containing the full builds row data" | Debezium, Kafka, `builds` table, Builder Services | HIGH | LOW |
| AD-24 | Implement environment management as a synchronous FastAPI REST service with Pydantic validation | Explicit in stack and contract sections | FastAPI, Python, Pydantic, `/environments` API | HIGH | MEDIUM - framework versions and auth middleware are unspecified |
| AD-25 | Scope environment reads by team and derive write permissions from creator or team-admin role | Explicit in endpoint descriptions | environment-manager-api, auth token source, `environments` table | HIGH | MEDIUM - depends on unspecified auth/role system |
| AD-26 | Derive `team_id` and creator identity from the authenticated user's token | Explicit: POST extracts both fields from the token | environment-manager-api, auth system, `environments` table | HIGH | MEDIUM - token schema is absent |
| AD-27 | Reject API writes to Git-managed environments | Explicit: global rule rejects POST/PUT/DELETE against `management_type = 'GIT'` records | environment-manager-api, `environments` table | HIGH | HIGH - `management_type` is referenced but not present in schema |
| AD-28 | Apply optimistic locking on environment writes using the `version` field | Explicit: all writes "must implement optimistic locking" | environment-manager-api, `environments` table | HIGH | LOW |
| AD-29 | Automatically assign expiration timestamps to ephemeral environments | Explicit in POST contract and use case | environment-manager-api, `environments` table | HIGH | MEDIUM - cleanup mechanism is not specified |
| AD-30 | Fix build timeout handling around a 30-minute deadline | Explicit in timeout workflow and use case | Timeout Service, Kafka, Builders, Orchestrator | HIGH | LOW |
| AD-31 | Provide a debugging UI with Gantt views, filtered failure logs, and source-code links keyed by `git_ref` | Explicit in use case | Custom Frontend, Kibana, Elasticsearch, Git | HIGH | MEDIUM - required integrations are only partially specified |

## 4. Cross-document dependencies

| ID | Direction | Component(s) | Dependency detail | Likely linked document(s) |
|---|---|---|---|---|
| CD-01 | Assumes | Authenticated user token issuer | The API requires tokens that contain `team_id`, `created_by_user_id`/user identity, and enough claims to infer team membership | `auth-v5.md` |
| CD-02 | Assumes | Team-admin authorization policy source | PUT/DELETE require "team admin role" checks, but the role system and decision engine are not defined here | `auth-v5.md` |
| CD-03 | Assumes | Artifact registry/object store behind `artifact_url` | Build completion and deployment-ready payloads reference OCI-style artifact URLs, but the storage system is unnamed | `platform-v2.md` or adjacent delivery spec |
| CD-04 | Assumes | Final deployment executor | `dev.platform.deployment.ready.v1` is emitted, but the service that consumes it and performs deployment is outside this document | `platform-v2.md` |
| CD-05 | Assumes | Environment provisioner/teardown runtime | The Orchestrator reacts to environment CDC events to create, update, or tear down environments, but the runtime operations are unspecified here | `platform-v2.md` |
| CD-06 | Assumes | Protected SCM hosting and webhook delivery | Git-managed flow requires protected branches, PR approval, merge hooks, and repository fetch semantics | Enterprise SCM / GitOps platform spec |
| CD-07 | Assumes | Shared cache backend / VFS product | The Dagger cache design depends on a shared VFS, but capacity, product choice, and failure semantics live elsewhere | `platform-v2.md` or storage/infra spec |
| CD-08 | Assumes | Observability/UI hosting | Kibana or a custom frontend must exist to render structured logs, Gantt views, and hyperlinks | `platform-v2.md` |
| CD-09 | Assumes | Source-code browser / SCM link resolver | The debugging use case requires direct links to code at the specific `git_ref`, but no repository browser is specified here | Enterprise SCM / developer tooling spec |
| CD-10 | Assumes | Platform-team identity registry | Git-managed records are stamped with `platformTeamId`/`platformTeamID`, but that identifier is not defined here | Org/auth governance spec |
| CD-11 | Assumes | Secrets, TLS, and service credentials | Kafka, PostgreSQL, Git, webhooks, and the API all need credentials and secure transport, but none are defined here | `auth-v5.md` and platform security spec |
| CD-12 | Provides | `platform.builds.v1` and build event types | Other specs can depend on a canonical build-task/start/completion event contract | `platform-v2.md`, operational tooling, UI specs |
| CD-13 | Provides | `platform.deployments.v1` readiness event | Other specs can treat `dev.platform.deployment.ready.v1` as the handoff point into deployment execution | `platform-v2.md` |
| CD-14 | Provides | `platform.environments.cdc.v1` | Other specs can consume a single immutable event stream for environment changes regardless of source | `platform-v2.md`, audit/ops tooling |
| CD-15 | Provides | Environment management API contract | Other specs can build CLI/UI/auth integrations against the `/environments` CRUD contract and ownership rules | `auth-v5.md`, platform API/client specs |
| CD-16 | Provides | PostgreSQL schemas for deployments/builds/environments | Other docs can reuse these tables and field contracts as the control-plane data model | `platform-v2.md`, migration/ops specs |

## 5. Implementation units

| Unit ID | Title | Description | Dependencies | Components involved | Estimated complexity | Can be parallelized with |
|---|---|---|---|---|---|---|
| `db-deployments-schema` | Create `deployments` schema | Add the `deployments` table with deployment ID, expected build count, status enum, and timestamps. This is the root aggregate for multi-service build orchestration. | None | PostgreSQL, `deployments` table | S | `db-environments-schema`, `dagger-cache-contract`, `gitops-static-repo-workflow` |
| `db-builds-schema` | Create `builds` schema | Add the `builds` table with deployment FK, service identity, git ref, status fields, artifact URL, version, and uniqueness by deployment/service. This captures the per-artifact state Debezium will publish. | `db-deployments-schema` | PostgreSQL, `builds` table | S | `db-environments-schema`, `dagger-cache-contract` |
| `db-environments-schema` | Create `environments` schema | Add the `environments` table with identity, team ownership, `spec`, creator metadata, timestamps, expiration, and versioning. The implementation must also resolve the spec's missing or inconsistent fields such as `environment_size` and `management_type`. | None | PostgreSQL, `environments` table | M | `db-deployments-schema`, `dagger-cache-contract`, `gitops-static-repo-workflow` |
| `kafka-build-contracts` | Provision build topics and event schemas | Define `platform.builds.v1` and the three build event types, including the Debezium envelope for task events and JSON payloads for started/completed events. This creates the canonical message contract for builders and the orchestrator. | `db-builds-schema` | Kafka, Debezium, `platform.builds.v1`, `builds` table | S | `dagger-cache-contract`, `gitops-static-repo-workflow`, `environment-api-read-path` |
| `debezium-builds-cdc` | Publish build-row changes to Kafka | Configure Debezium to capture committed `builds` inserts from the PostgreSQL WAL and publish `dev.platform.build.task.v1` messages. This is the asynchronous handoff from state registration into build execution. | `db-builds-schema`, `kafka-build-contracts` | PostgreSQL WAL, Debezium, Kafka, `builds` table, `platform.builds.v1` | M | `dagger-cache-contract`, `environment-api-read-path` |
| `orchestrator-deployment-registration` | Register deployments and builds atomically | Implement the orchestration entrypoint that writes one `deployments` row plus one `builds` row per artifact in a single transaction. It establishes the authoritative initial state for every deployment. | `db-deployments-schema`, `db-builds-schema` | Orchestrator, PostgreSQL, `deployments`, `builds` | M | `dagger-cache-contract`, `gitops-static-repo-workflow`, `environment-api-read-path` |
| `dagger-cache-contract` | Implement granular Dagger cache keying | Implement the cache-key contract `v1-{service_name}-{cache_type}-{git_ref_slug}-{content_hash}` and ensure cache volumes use highly granular keys over shared storage. This unit includes deriving `content_hash` values (SHA256) from ecosystem lockfiles and equivalent inputs. | None | Dagger, Shared VFS, SHA256 | M | `db-deployments-schema`, `db-environments-schema`, `gitops-static-repo-workflow` |
| `builder-execution-service` | Run build tasks and emit lifecycle events | Implement the ephemeral builder worker that consumes `dev.platform.build.task.v1`, starts a Dagger build, publishes `dev.platform.build.started.v1`, and emits `dev.platform.build.completed.v1` with status and artifact URL. The worker must tolerate restarts without corrupting orchestration state. | `kafka-build-contracts`, `debezium-builds-cdc`, `dagger-cache-contract` | Builder Services, Dagger, Kafka, `platform.builds.v1` | L | `environment-api-read-path`, `gitops-static-repo-workflow` |
| `timeout-management-service` | Detect and report timed-out builds | Implement the stateful timer service that tracks active build IDs, schedules 30-minute timers on `build.started`, cancels them on `build.completed`, and publishes synthetic timeout failures if timers fire. This preserves a single failure event contract. | `kafka-build-contracts` | Timeout-management Service, Kafka, `platform.builds.v1` | M | `deployment-ready-aggregation`, `environment-api-read-path`, `gitops-static-repo-workflow` |
| `deployment-ready-aggregation` | Aggregate successful builds and emit readiness | Implement the orchestrator-side aggregation logic that updates build state, increments the Redis success counter for each successful build, and emits `dev.platform.deployment.ready.v1` once `expected_build_count` is met. It is the only unit in this document that bridges build completion into deployment handoff. | `db-deployments-schema`, `db-builds-schema`, `kafka-build-contracts`, `orchestrator-deployment-registration` | Orchestrator, Redis, Kafka, PostgreSQL, `platform.deployments.v1` | M | `environment-api-read-path`, `gitops-static-repo-workflow` |
| `build-log-streaming` | Stream Dagger logs into Elasticsearch | Capture all Dagger execution logs, annotate them with `build_id`, and write them into an Elasticsearch datastream. This creates the raw observability substrate for debugging and traceability. | `builder-execution-service` | Dagger, Elasticsearch, Builder Services | M | `environment-api-read-path`, `gitops-static-repo-workflow` |
| `elastic-ingest-enrichment` | Parse and enrich pipeline logs | Implement the Elasticsearch ingest pipeline that structures raw logs into queryable fields and joins contextual metadata by `build_id`. This is the basis for the richer debugging UI promised by the use cases. | `db-builds-schema`, `build-log-streaming` | Elasticsearch, Elasticsearch Ingest Pipeline, `builds` table | M | `environment-api-read-path`, `gitops-static-repo-workflow` |
| `debug-ui-build-traceability` | Build the debugging interface | Deliver the UI capabilities promised by the spec: Gantt-style deployment views, exact filtered links to failure lines, and source links to the tested `git_ref`. Whether implemented in Kibana or a custom frontend, this is the user-facing observability surface. | `build-log-streaming`, `elastic-ingest-enrichment` | Kibana, Custom Frontend, Elasticsearch, Git | L | `environment-api-read-path`, `gitops-static-repo-workflow` |
| `environment-api-read-path` | Implement environment read endpoints | Implement `GET /environments` and `GET /environments/{name}` with team-based scoping. This unit owns pagination/listing semantics if the modernization effort chooses to add them. | `db-environments-schema` | environment-manager-api service, FastAPI, Python, Pydantic, `/environments` REST API | M | `kafka-build-contracts`, `debezium-builds-cdc`, `gitops-static-repo-workflow` |
| `environment-api-write-path` | Implement environment create/update/delete | Implement POST, PUT, and DELETE with token-derived ownership, creator-or-team-admin authorization, optimistic locking, auto-expiration for ephemeral records, and hard rejection of Git-managed rows. This is the API-managed path for dynamic environments. | `db-environments-schema`, `environment-api-read-path` | environment-manager-api service, FastAPI, Pydantic, `environments` table, `/environments` REST API | L | `gitops-static-repo-workflow`, `deployment-ready-aggregation` |
| `debezium-environments-cdc` | Publish environment changes to Kafka | Configure Debezium to emit immutable before/after events for `environments` row changes onto `platform.environments.cdc.v1`. This unit makes API-driven and Git-driven changes uniform for downstream consumers. | `db-environments-schema` | PostgreSQL WAL, Debezium, Kafka, `environments` table, `platform.environments.cdc.v1` | M | `timeout-management-service`, `build-log-streaming` |
| `gitops-static-repo-workflow` | Define Git-managed environment source contract | Define the repository layout, JSON file naming, protected-branch policy, PR approval rule, and webhook trigger for static environments. This is the control surface for long-lived environment changes. | None | Static environments Git repository, Git, Pull Request workflow, Webhook, JSON configuration files | M | `db-deployments-schema`, `db-environments-schema`, `environment-api-read-path` |
| `gitops-controller-reconciler` | Reconcile Git state into the environment table | Implement the controller that fetches configuration files after a protected-branch merge and reconciles them into PostgreSQL with create/update/delete semantics. It must stamp managed rows as Git-owned/system-owned using the agreed metadata fields. | `db-environments-schema`, `gitops-static-repo-workflow` | GitOps Controller, Git repository, PostgreSQL, `environments` table | L | `build-log-streaming`, `timeout-management-service` |
| `orchestrator-environment-change-consumer` | React to environment CDC events | Implement the orchestrator-side consumer for `platform.environments.cdc.v1` so INSERT, UPDATE, and DELETE events trigger create/update/teardown workflows. This is the point where state declarations become runtime actions. | `debezium-environments-cdc` | Orchestrator, Kafka, `platform.environments.cdc.v1` | M | `build-log-streaming`, `timeout-management-service` |
| `ephemeral-env-expiration-cleanup` | Enforce TTL-based environment cleanup | Implement the automated cleanup path implied by `expiration_timestamp` and the ephemeral environment use case. This unit should emit the same state transitions and orchestration signals as any other environment deletion path. | `db-environments-schema`, `debezium-environments-cdc`, `orchestrator-environment-change-consumer` | environment-manager-api service, Orchestrator, PostgreSQL, Kafka, `environments` table | M | `debug-ui-build-traceability` |

## 6. Outdated or questionable elements

1. Dagger is the center of the CI design, but the modernization baseline may already have moved to a different CI system; this makes several sections potentially obsolete at the platform level.
2. `dagger.CacheSharingMode.LOCKED` is a very specific product/API decision, not a durable architectural abstraction.
3. The shared VFS cache host is critical to the design but completely unnamed, which is risky for a 2026 modernization effort.
4. The GitOps path introduces a custom GitOps controller even though adjacent legacy platform material already leans on Flux-style reconciliation; this may be duplicated functionality.
5. `Kibana / Custom Frontend` leaves a core user-facing subsystem unresolved, which is too vague for implementation planning.
6. The observability model is Elastic-centric here, while neighboring platform material also references Grafana/VictoriaMetrics/Elastic APM, suggesting cross-document overlap.
7. The `environments` table SQL is malformed: `environment_size,` appears without a type or constraints.
8. `management_type = 'GIT'` is central to the API authorization contract and GitOps flow, but `management_type` is absent from the published schema.
9. Git-managed record metadata is inconsistent: `CREATED_BY`, `created_by_user_id`, `platformTeamId`, and `platformTeamID` all appear as if they were the same fields.
10. The GitOps source format is only described as JSON files such as `production.json`; no schema or validation contract is defined.
11. `artifact_url` is required in build completion and deployment-ready flows, but the registry or artifact storage system is never named in this document.
12. The use case promises automated cleanup of ephemeral environments, but no scheduler, controller, or workflow is specified for it.
13. The debugging use case promises direct source-code hyperlinks keyed by `git_ref`, but no SCM provider, URL contract, or link-resolution mechanism is defined.

## 7. Missing elements

1. No failure-handling or retry semantics are defined for Debezium, Kafka producers/consumers, or the GitOps controller.
2. No idempotency strategy is specified for duplicate `build.completed` events, duplicate CDC delivery, or controller replays.
3. No partitioning, ordering, or consumer-group strategy is defined for Kafka topics, even though orchestration depends on event order.
4. No backup/recovery or high-availability plan is defined for PostgreSQL, Kafka, Redis, or Elasticsearch.
5. No cost model is provided for builder concurrency, cache storage, Kafka retention, or Elasticsearch log volume.
6. No security hardening is defined for API auth, webhook verification, database credentials, Kafka credentials, or service-to-service TLS.
7. No schema is defined for the `spec` JSONB column in `environments` or for the Git-managed JSON files.
8. No migration/versioning strategy is specified for the database schemas or the event contracts.
9. No final deployment workflow is specified after `dev.platform.deployment.ready.v1` is published.
10. No operational runbooks are defined for timeout storms, stuck builds, failed reconciliations, or Redis counter drift.
11. No monitoring or alerting requirements are defined for the Orchestrator, Builder Services, Timeout Service, API service, or GitOps controller.
12. No retention, archival, or deletion policy is specified for build logs, build records, deployment records, or expired environments.
13. No rollback or compensation model is defined for partial failures in build orchestration or environment reconciliation.

## 8. Raw statistics

- Total components mentioned: 32
- Total architectural decisions: 31
- Total implementation units: 20
- Total cross-document dependencies: 16
- Total outdated/questionable flags: 13
