## 1. Scope and document intent

This document is a legacy architecture specification for a CI/CD and environment-management platform. It covers build orchestration, event transport, environment lifecycle control, GitOps/API change paths, and observability. It is not an implementation plan; it is a combined vision/specification artifact with concrete contracts (tables, topics, events, endpoints) and workflow sketches.

## 2. Component inventory

| Component | Kind | Role in document | Notes |
| --- | --- | --- | --- |
| CI/CD and Environment Management platform | Internal platform | Overall system being evolved | Explicit: the document defines the architecture for this platform (lines 1, 5). |
| Dagger | Technology | Core CI/CD execution engine | Explicit: named as the engine for pipeline logic and later as the orchestrator/build runtime (lines 17, 39, 70, 227, 259). |
| Dagger cache volumes | Internal subsystem | Granular cache layer for parallel builds | Explicit: cache volumes are central to the throughput strategy and have a formal keying contract (lines 39, 91-98, 259). |
| shared VFS | Storage substrate | Shared backing store for Dagger caches | Explicit: caches are hosted on a shared VFS (line 39). Inference: this is a separate storage dependency, not just an implementation detail. |
| PostgreSQL | Technology | Canonical transactional state store | Explicit: canonical source of truth for system state, build status, and environment configs (lines 21, 40, 53, 64, 83, 228, 244). |
| PostgreSQL Write-Ahead Log (WAL) | Database mechanism | CDC source for Kafka publication | Explicit: Debezium streams committed changes from the WAL (lines 23, 40, 54, 65, 84, 245). |
| Kafka | Technology | Central asynchronous event backbone | Explicit: central communication backbone and topic host for build/deployment/environment events (lines 22, 40-45, 54-59, 65-66, 76-78, 84-85). |
| Debezium | Technology | CDC bridge from PostgreSQL to Kafka | Explicit: streams committed DB state changes to Kafka and underpins both build and environment flows (lines 23, 40, 45, 54, 65, 84, 159, 198, 245-246). |
| Redis | Technology | Ephemeral state accelerator | Explicit: used for atomic counters and deployment aggregation (lines 27, 58-59, 232). |
| deployment-specific counter | Internal subsystem | Tracks completed successful builds per deployment | Explicit: incremented in Redis and compared with `expected_build_count` before publishing deployment readiness (lines 58-59, 232). |
| Elasticsearch | Technology | Log storage and query engine | Explicit: stores and queries structured pipeline logs (lines 28, 41, 70-72). |
| Elasticsearch datastream | Internal subsystem | Destination for Dagger log output | Explicit: Dagger logs are streamed to an Elasticsearch datastream (line 70). |
| Elasticsearch Ingest Pipeline | Internal subsystem | Parses and enriches raw build logs | Explicit: structures logs and enriches them with context from `build_id` (lines 41, 71). |
| Kibana | Product/UI | One possible observability UI | Explicit: named as a visualization layer over Elasticsearch (lines 29, 72). |
| Custom Frontend | Internal subsystem | Alternative observability UI | Explicit: paired with Kibana as the debugging UI layer (line 29). Inference: the document does not resolve whether Kibana, a bespoke UI, or both are required. |
| FastAPI (Python) | Technology | Framework for the environment-management API | Explicit: web framework for the synchronous REST API (line 33). |
| Pydantic | Technology | Request/response schema enforcement | Explicit: validation library for API contracts (line 34, line 219). |
| Orchestrator | Internal subsystem | Central coordinator for builds, deployments, and environment reactions | Explicit: writes build/deployment state, consumes completion events, publishes readiness, and reacts to environment CDC events (lines 53, 57-59, 66, 85, 227-232, 247, 254). |
| Builder Service / Ephemeral Builder services | Internal subsystem | Executes individual build tasks | Explicit: consumes build tasks and emits started/completed events (lines 55-56, 160-180, 230). |
| timeout-management service | Internal subsystem | Detects long-running builds and emits timeout failures | Explicit: stateful service that subscribes to build events and publishes standardized timeout failures (lines 41, 76-78, 170, 236-239, 262). |
| environment-manager-api service | Internal subsystem | Synchronous API for API-managed environments | Explicit: manages environment state and enforces authz/locking rules (lines 43, 200-219, 243-247, 263). |
| GitOps controller service | Internal subsystem | Syncs Git-managed static environment config into PostgreSQL | Explicit: fetches config files from Git and reconciles the `environments` table (lines 44, 82-85, 151, 251-254, 264). |
| static environments Git repository | External control surface | Source of truth for static/protected environments | Explicit: protected Git repository for production/staging and JSON config changes via PRs (lines 9, 44, 82, 251-252, 264). |
| `deployments` table | Data schema | Tracks deployment-level state | Explicit: formal PostgreSQL schema and orchestration anchor (lines 53, 102-113, 228). |
| `builds` table | Data schema | Tracks per-service build state | Explicit: formal PostgreSQL schema, Debezium source, and builder task source (lines 54, 115-132, 159, 228-231). |
| `environments` table | Data schema | Stores environment definitions and versioned state | Explicit: formal PostgreSQL schema and convergence point for API/GitOps changes (lines 64, 83, 138-151, 198, 244, 253). |
| `platform.builds.v1` | Kafka topic | Carries build task and lifecycle events | Explicit: topic for task, started, and completed events (lines 54, 76, 155-180, 229, 236). |
| `platform.deployments.v1` | Kafka topic | Carries deployment-ready events | Explicit: readiness topic published by the orchestrator (lines 59, 182-194, 232). |
| `platform.environments.cdc.v1` | Kafka topic | Unified audit/event stream for environment state changes | Explicit: used for API- and Git-originated environment change events (lines 45, 65, 84, 196-198, 246, 254, 263). |
| `dev.platform.build.task.v1` | Event contract | Build work item emitted from CDC | Explicit: Debezium publishes this event for new build rows (lines 54, 157-159, 229). |
| `dev.platform.build.started.v1` | Event contract | Signals build start | Explicit: emitted by builders and consumed by timeout management (lines 56, 76, 160-168, 230, 237). |
| `dev.platform.build.completed.v1` | Event contract | Standard completion/failure signal | Explicit: emitted by builders or timeout management; consumed by orchestrator (lines 41, 56-57, 78, 169-180, 230-231, 238-239, 262). |
| `dev.platform.deployment.ready.v1` | Event contract | Signals readiness for final deployment phase | Explicit: emitted when successful build count reaches the expected total (lines 59, 184-194, 232). |
| `/environments` REST interface | API surface | CRUD interface for API-managed environments | Explicit: POST/GET/PUT/DELETE contract under `/environments` and `/environments/{name}` (lines 63, 202-219, 263). |
| JSON configuration file / `production.json` | Config artifact | Git-managed representation of static environment state | Explicit: static environments are changed by editing JSON files in Git; `production.json` is the example (lines 251, 264). |
| debugging interface | Internal subsystem | User-facing diagnostics surface for builds/logs | Explicit: structured logs are queried and visualized in a debugging interface (lines 72, 261). |

## 3. Architectural decisions

| Decision | Evidence from document | Rationale in document | Confidence | Modernization risk |
| --- | --- | --- | --- | --- |
| Use Dagger as the CI/CD execution engine | Explicit: "Dagger: The engine for defining and executing all CI/CD pipeline logic" (line 17). | Explicit: isolated-container execution is the core build primitive for the platform (lines 17, 227, 259). | high | high |
| Execute pipeline logic inside isolated containers | Explicit: Dagger executes pipeline logic "within isolated containers" (line 17). | Explicit: isolation is treated as part of the execution model, not an optional detail (line 17). | high | medium |
| Optimize build throughput through granular, content-addressed caching | Explicit: multi-layered caching is required; cache key format is formalized as `v1-{service_name}-{cache_type}-{git_ref_slug}-{content_hash}` (lines 39, 93-98, 259). | Explicit: minimizing lock contention is a prerequisite for parallel execution (line 39). | high | medium |
| Back Dagger caches with a shared VFS and `dagger.CacheSharingMode.LOCKED` | Explicit: `LOCKED` sharing is applied to granular cache volumes hosted on a shared VFS (line 39). | Explicit: the VFS is intentionally turned into a partitioned keystore instead of a contention hotspot (line 39). | high | high |
| Treat PostgreSQL as the canonical source of current state | Explicit: PostgreSQL is the "canonical source of truth" for system state (line 21). | Explicit: all state modifications must commit there first before downstream publication (line 40). | high | low |
| Make the Transactional Outbox pattern foundational for state changes | Explicit: "System-wide resilience and data integrity shall be achieved by implementing the Transactional Outbox pattern as the foundational principle" (line 40). | Explicit: ordered, reliable propagation of committed state is required for both builds and environment config (line 40). | high | medium |
| Publish committed database changes through Debezium CDC from WAL to Kafka | Explicit: Debezium captures committed changes from the WAL and publishes them to Kafka (lines 23, 40, 54, 65, 84, 245). | Explicit: this is the mechanism that makes the event stream a reflection of committed state (line 40). | high | medium |
| Treat Kafka as the immutable, auditable source of truth over time | Explicit: Kafka is the central async backbone; the event stream is "immutable" and "auditable" over time (lines 22, 40, 45). | Explicit: auditability and decoupled orchestration depend on downstream consumers reacting to the same event stream (lines 40, 45). | high | medium |
| Register deployment/build state in PostgreSQL before any builder work begins | Explicit: the Orchestrator first writes `deployments` and `builds` rows with `PENDING` status in one transaction (lines 53, 228). | Explicit: build work is then derived from CDC of those rows, rather than from direct imperative dispatch (lines 54, 229). | high | low |
| Drive build execution with ephemeral builder workers consuming task events | Explicit: Ephemeral Builder services consume `dev.platform.build.task.v1` and emit started/completed events (lines 55-56, 230). | Explicit: this supports decoupled, horizontally scalable build execution (lines 7, 55-56). | high | medium |
| Use Redis atomic counting to decide when a deployment is ready | Explicit: Redis is used for atomic counters, and readiness is published when the counter matches `expected_build_count` (lines 27, 58-59, 232). | Explicit: readiness is gated on all required artifacts succeeding (lines 59, 232, 260). | high | medium |
| Centralize observability around structured logs in Elasticsearch with UI access | Explicit: Dagger logs are enriched and indexed in Elasticsearch, then visualized in Kibana or a custom frontend (lines 28-29, 41, 70-72). | Explicit: this enables debugging features such as log-to-code traceability and near real-time feedback (lines 8, 41, 261). | high | medium |
| Handle timeouts in a dedicated, stateful timeout-management service | Explicit: a dedicated service subscribes to build events, tracks active builds, and publishes timeout failures (lines 41, 76-78, 236-239). | Explicit: failure detection is deliberately decoupled from the core orchestrator (line 41). | high | medium |
| Standardize failure signaling on `dev.platform.build.completed.v1` | Explicit: timeout management publishes the same completion event shape used by builders; any new monitoring component may do the same (lines 41, 78, 169-180, 239, 262). | Explicit: extensibility comes from allowing multiple producers to emit the same standardized failure signal (line 41). | high | medium |
| Use a hybrid environment-management model: API-managed dynamic environments plus Git-managed static environments | Explicit: the platform supports "two distinct but complementary paradigms" (lines 42-44). | Explicit: API gives flexibility for ephemeral development/testing, while Git gives control and review for static environments (lines 9, 42-44, 263-264). | high | medium |
| Converge both environment-management paths at PostgreSQL plus a shared CDC topic | Explicit: both workflows converge at the database and emit to `platform.environments.cdc.v1` (lines 45, 65, 84, 246, 254). | Explicit: downstream consumers should not need to know whether a change came from Git or the API (line 45). | high | low |
| Require PR-reviewed changes on a protected branch for static environments | Explicit: static environment Git pushes happen through a PR with mandatory approval to a protected `main` branch (lines 82, 251-252, 264). | Explicit: this is the mechanism for peer-reviewed, version-controlled change management of critical infrastructure (lines 9, 82, 251-252, 264). | high | medium |
| Mark GitOps-managed environment records as system-owned platform records | Explicit: GitOps-managed records use `created_by_user_id = "system"` and the platform team ID; later workflow text adds `management_type: 'GIT'` (lines 151, 202, 253). | Explicit: these markers separate Git-managed records from user-managed records; inference: they are also used for authorization and ownership boundaries. | medium | medium |
| Reject API writes against Git-managed environments | Explicit: the API must reject write requests targeting environments where `management_type = 'GIT'` (line 202). | Explicit: Git-managed environments are exclusively controlled through the GitOps workflow (line 202). | high | low |
| Use optimistic locking for environment writes | Explicit: all environment write operations must check and increment the `version` field (line 219). | Explicit: versioned writes are the chosen concurrency-control mechanism for environment records (line 219). | high | low |

## 4. Implementation units

| Unit | What would need to be built/configured | Dependencies | Why it exists |
| --- | --- | --- | --- |
| Dagger pipeline definitions | Containerized CI/CD pipelines for the services/artifacts the platform builds | Dagger, service catalog, source repositories | Because Dagger is the declared execution engine for all pipeline logic (lines 17, 227, 259). |
| Cache key computation and cache-volume management | Logic that computes `v1-{service_name}-{cache_type}-{git_ref_slug}-{content_hash}` and applies it consistently | Dagger cache volumes, Git refs, content hashing inputs | Because throughput depends on granular content-addressed caches rather than coarse shared caches (lines 39, 93-98, 259). |
| Shared VFS cache backing | Provisioning/configuration of the shared cache storage substrate | shared VFS, Dagger cache mode | Because the caching strategy explicitly assumes shared-VFS-backed locked cache volumes (line 39). |
| Orchestrator deployment/build registration | Code that creates deployment/build records in a single transaction | PostgreSQL, `deployments` table, `builds` table | Because build execution is triggered from persisted state, not direct task dispatch (lines 53-54, 227-229). |
| Deployment/build database schemas | Creation and management of `deployments` and `builds` schemas | PostgreSQL | Because these tables are canonical state for orchestration and CDC (lines 102-132). |
| Build-task CDC pipeline | Debezium connector/config for `builds` changes into `platform.builds.v1` | PostgreSQL WAL, Debezium, Kafka | Because builder work items come from CDC of the `builds` table (lines 54, 157-159, 229). |
| Builder worker runtime | Service that consumes build tasks and emits started/completed events | Kafka, Dagger, artifact storage | Because the design offloads actual build execution to ephemeral builders (lines 55-56, 230). |
| Build completion state updater | Consumer that updates `builds` status after completion events | Orchestrator, Kafka, PostgreSQL | Because completed events must be reflected back into canonical state (lines 57, 231). |
| Redis success aggregation and deployment-ready publishing | Counter increment/read logic plus `dev.platform.deployment.ready.v1` publication | Redis, Orchestrator, Kafka | Because deployment proceeds only after all required artifacts succeed (lines 58-59, 232). |
| Timeout-management service | Stateful worker that tracks active builds and synthesizes timeout failures | Kafka, timeout state store, standardized completion event | Because timeout detection is intentionally separated from core orchestration (lines 41, 76-78, 236-239). |
| Dagger log shipping | Stream Dagger logs to the Elasticsearch datastream with `build_id` metadata | Dagger, Elasticsearch datastream | Because observability starts from build logs being emitted into search/storage (line 70). |
| Log parsing/enrichment pipeline | Elasticsearch Ingest Pipeline rules that structure and enrich logs | Elasticsearch, metadata lookup keyed by `build_id` | Because raw logs must become queryable fields and traceable UI data (lines 41, 71). |
| Debugging interface | Kibana dashboards, a custom frontend, or both for log/build visualization | Elasticsearch, UI layer, source-code URL model | Because the document promises log-to-code traceability, Gantt-style views, and fast debugging (lines 29, 72, 261). |
| Environment database schema | Creation and management of the `environments` table and its concurrency fields | PostgreSQL | Because both API- and Git-managed environments converge on this table (lines 138-151, 244, 253). |
| Environment manager REST API | CRUD endpoints under `/environments` and `/environments/{name}` | FastAPI, Pydantic, PostgreSQL | Because API-managed ephemeral environments are a first-class workflow (lines 43, 200-219, 243-247, 263). |
| API authorization and token extraction | Logic for team scoping, creator checks, and team-admin rules | Authenticated user token, team/role model | Because the API contract depends on extracted `team_id`, creator identity, and admin roles (lines 205, 208, 211-218, 243). |
| Optimistic locking for environment writes | Version-checking update/delete behavior on `environments` | `version` field, API write handlers | Because the contract explicitly requires optimistic locking on all writes (line 219). |
| Static environments repository and review flow | Repo layout, JSON config files, protected-branch policy, PR workflow | Git hosting, branch protection, reviewers | Because Git-managed static environments are changed through reviewed PRs in a protected repo (lines 44, 82, 251-252, 264). |
| GitOps controller reconciler | Service that fetches Git state and reconciles `environments` rows | Git repository, PostgreSQL, ownership markers | Because Git-managed changes are applied to the platform through DB reconciliation (lines 44, 82-85, 151, 253-254). |
| Environment CDC pipeline | Debezium connector/config for `environments` changes into `platform.environments.cdc.v1` | PostgreSQL WAL, Debezium, Kafka | Because both API and Git changes are broadcast through the same auditable topic (lines 45, 65, 84, 198, 245-246, 254). |
| Environment-event consumer and actuator | Consumer that translates environment CDC events into create/update/teardown actions | Orchestrator, `platform.environments.cdc.v1`, runtime control plane | Because the orchestrator is expected to react identically regardless of the change source (lines 66, 85, 247, 254). |
| Ephemeral environment expiration handling | Mechanism that enforces `expiration_timestamp` and automated cleanup | `environments` table, scheduler/worker, environment teardown path | Because the use case says ephemeral environments are automatically cleaned up when they expire (lines 205, 263). |
| Source-code deep linking | Logic that maps `git_ref` and failure context into source-code URLs | Git metadata, debugging interface | Because the UI promise includes direct links to the specific commit that was tested (line 261). |

## 5. Cross-document dependencies

| Dependency | Depends on what | Why it is cross-document | Confidence |
| --- | --- | --- | --- |
| Authentication and authorization model | Authenticated user token shape, claim extraction, team-admin role definitions | This document requires token-derived `team_id` and creator identity plus team-admin authorization, but does not define the auth system itself (lines 205, 214-218, 243). | high |
| Platform team identity source | Canonical source for `platformTeamID` / platform team's ID | GitOps-managed records are tagged with a platform-team identifier, but that identifier is not defined here (lines 83, 151, 253). | high |
| Environment specification schema | Structure and validation rules for `spec JSONB` and Git JSON config files | The document stores environment state in `spec`, but never defines the schema or how JSON files map onto it (lines 143, 251, 264). | high |
| Environment runtime control plane | Actual system that creates, updates, and tears down environments | The orchestrator is said to react to environment events, but the target control plane is outside this document (lines 66, 85, 247, 254). | high |
| Final deployment executor | Whatever consumes `dev.platform.deployment.ready.v1` and performs deployment | The document stops at publishing readiness and never defines the final deployment phase (lines 59, 184-194, 232). | high |
| Artifact storage/registry | Concrete backend for `artifact_url` / OCI artifacts | Build completion and deployment-ready payloads carry artifact URLs, but no registry is named (lines 127, 178, 191-192, 230). | high |
| Git hosting / PR / webhook control plane | Repository host, branch protection, webhook delivery/authentication | Static environments rely on PR approval, protected branches, and webhook-triggered sync, none of which are specified here (lines 82, 251-252). | high |
| Service catalog / deployment composition | Source of truth for `service_name` values and `expected_build_count` | The orchestration flow assumes a known set of services/artifacts per deployment, but that catalog is not defined in this document (lines 95, 108, 122, 228, 260). | medium |
| Shared VFS/storage platform | Concrete implementation and ownership of the shared cache substrate | The cache design depends on a shared VFS, but the storage platform is not identified here (line 39). | high |
| Source-code hosting model | URL pattern/provider mapping for `git_ref` deep links | The debugging UI promises links to the tested commit, but the source-code host and link format are external (line 261). | medium |
| Network policy / environment payload semantics | Meaning of `production.json` and the environment config fields it changes | The GitOps use case uses a production network-policy change as an example, but the network-policy model is not defined here (line 264). | medium |
| Observability product boundary | Whether the debugging surface is part of a broader platform UI | The document names "Kibana / Custom Frontend" but does not define the larger UI architecture elsewhere (line 29, line 261). | medium |

## 6. Outdated or questionable items

| Item | Why questionable | Likely modernization direction |
| --- | --- | --- |
| Dagger | External conflict marker: the user explicitly wants `Buildkite` preserved as the preferred modernization target over `Dagger`. The legacy spec is Dagger-centric throughout. | Preserve as a direct conflict marker for later merge; prefer evaluating `Buildkite` rather than carrying Dagger forward by default. |
| GitOps controller service | The legacy design assumes a bespoke controller service. External conflict marker: the user wants `Flux` preserved as the preferred modernization target over `Argo`, and the modern target may also differ from a bespoke controller. | Preserve as a conflict marker; later merge should compare the bespoke controller against a `Flux`-aligned realization and should not auto-select `Argo`. |
| shared VFS plus `dagger.CacheSharingMode.LOCKED` | This is a very specific throughput optimization tied to the legacy Dagger design and a particular cache-contention model. | Re-evaluate under the modern CI runner; keep only if the replacement stack still needs shared locked caches. |
| PostgreSQL + Debezium + Kafka + Redis stack | The design couples four infrastructure systems for one control plane. That may be justified, but it is a high-complexity legacy choice. | Reassess whether the modern platform still needs all four layers or can collapse some responsibilities. |
| Kibana / Custom Frontend split | The document never decides whether observability is Kibana, a bespoke UI, or both. | Force a single UI/product boundary decision during merge. |
| Fixed 30-minute timeout | The timeout appears as a hardcoded workflow constant rather than a typed policy. | Move toward configurable timeout policy per build class or workload. |
| GitOps ownership sentinels (`"system"`, platform team ID, `management_type = 'GIT'`) | The ownership model relies on magic values and partially inconsistent field naming across sections. | Replace with a clearer typed ownership/provenance model if the surrounding schema survives. |
| JSON files in Git as the static-environment representation | The legacy doc uses ad hoc JSON files in Git but gives no schema or validation regime. | Add a typed config model or reconcile into whatever declarative format the merged platform standardizes on. |
| Redis success counter | The readiness gate is tracked in Redis even though build state already exists in PostgreSQL and Kafka. | Re-evaluate whether readiness can be derived without a separate mutable counter store. |
| Direct Dagger-to-Elasticsearch log streaming assumption | The document assumes logs flow straight from Dagger to Elasticsearch but does not define a shipper, collector, or buffering layer. | Reassess the log path under the modern runner and observability stack. |
| Provider framing | External conflict marker: later merge must preserve that provider choice may move beyond the original Vultr framing, even though this document is largely provider-agnostic. | Keep provider selection open and avoid binding the merged design to the old provider assumptions. |
| Legacy-spec fidelity | External conflict marker: the user expects the modernized platform to differ materially from these legacy specs. | Treat this index as source material for reconciliation, not as a target architecture to preserve verbatim. |

## 7. Missing or underspecified elements

| Gap | Why it matters | Confidence |
| --- | --- | --- |
| `environment_size` is present without a type or constraints in the `environments` schema | The table definition is incomplete as written and cannot be implemented literally from this spec (lines 138-149). | high |
| `management_type` is used in API/GitOps rules but missing from the `environments` schema | The API contract depends on this field for write rejection, but the schema never defines it (lines 202, 253 versus lines 138-149). | high |
| GitOps record markers are inconsistently named | The document alternates among `CREATED_BY`, `created_by_user_id`, `platformTeamId`, and "platform team's ID", which leaves the canonical schema unclear (lines 83, 151, 253). | high |
| No schema is given for `spec JSONB` | `spec` is the core environment payload, but its structure is completely unspecified (line 143). | high |
| No repository layout or file-to-row mapping is defined for static environment configs | The spec says engineers edit JSON files in Git, but it never defines naming conventions, directories, or how files map to environment rows (lines 82-83, 251, 264). | high |
| No webhook authentication, retry, or idempotency behavior is defined | The GitOps flow depends on a webhook trigger, but operational semantics for that integration are absent (line 82). | high |
| No auth/token claim model is defined | The environment API requires token-derived identity and team information, but this document does not define claim names or trust boundaries (line 205, lines 214-218). | high |
| No artifact registry or artifact retention model is named | `artifact_url` is a first-class field and deployment-ready payload element, but the backing registry is undefined (lines 127, 178, 191-192). | high |
| No final deployment phase is specified after `dev.platform.deployment.ready.v1` | The document emits readiness but never defines who consumes it or how deployment happens afterward (lines 59, 184-194, 232). | high |
| No concrete environment provision/update/teardown mechanism is defined | The orchestrator is said to react to environment CDC events, but the actual actuator/controller for those actions is missing (lines 66, 85, 247, 254). | high |
| No cleanup actor is defined for expired ephemeral environments | The use case promises automatic cleanup based on `expiration_timestamp`, but no workflow or service performs it (lines 205, 263). | high |
| No builder scheduling/execution substrate is identified | The spec names ephemeral builders but not how they are provisioned, isolated, autoscaled, or recovered (lines 55, 230, 260). | medium |
| No implementation details are given for the shared VFS | The caching design depends on this substrate, but there is no storage class, consistency model, or operational owner (line 39). | high |
| No Kafka consumer semantics are defined for retries, deduplication, or ordering edge cases | The design relies heavily on events and CDC, but operational correctness rules are omitted. | medium |
| No log retention, access-control, or cost model is defined for Elasticsearch/Kibana | Observability is central to the design, but storage and access posture are not specified. | medium |
| No concrete UI contract is given for Gantt views, filtered logs, or source-code hyperlinks | The use cases promise specific debugging UX features, but there are no interface contracts or data models for them (line 261). | medium |

## 8. Raw statistics

- Total components mentioned: 36
- Total architectural decisions: 20
- Total implementation units: 23
- Total cross-document dependencies: 12
- Total outdated/questionable flags: 12
