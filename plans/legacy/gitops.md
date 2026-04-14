# Specification for Platform Evolution: CI/CD and Environment Management

## 1.0 Goals

This document specifies the architecture for the evolution of the CI/CD and Environment Management platform. The primary goals of this evolution are as follows:
Achieve High-Throughput, Scalable CI: The platform must support a high degree of parallel build execution without performance degradation from resource contention, specifically within the caching layer.
Ensure Resilient and Robust Orchestration: The platform must orchestrate complex, multi-service builds through a fault-tolerant, event-driven system that is decoupled and scales horizontally.
Enhance Developer Experience and Observability: The platform must provide developers with advanced, actionable insights into pipeline execution, test results, and failures, coupled with near real-time feedback mechanisms.
Implement a Flexible, Auditable Configuration Model: The platform must support a hybrid model that combines the rigor of GitOps with the flexibility of an API. This dual approach allows for version-controlled, peer-reviewed management of static, long-lived environments (e.g., production, staging) via a protected Git repository, while also providing a dynamic, API-driven workflow for on-demand, ephemeral environments used in development and testing. This provides the appropriate control and convenience for each use case, while ensuring all changes are captured in an immutable, auditable event log.

## 2.0 Technology Stack

The implementation of the platform shall use the following technology stack.

### 2.1 Core Orchestration and Execution

Dagger: The engine for defining and executing all CI/CD pipeline logic within isolated containers. 1

### 2.2 Data and Eventing Backbone

PostgreSQL: The durable, transactional data store serving as the canonical source of truth for all system state, including build status and environment configurations. 1
Kafka: The high-throughput, distributed event streaming platform that forms the central communication backbone for all asynchronous communication between services. 1
Debezium: The Change Data Capture (CDC) platform used to stream all committed state changes from the PostgreSQL Write-Ahead Log (WAL) directly to Kafka topics. 1

### 2.3 Observability and State Management

Redis: An in-memory data store used as a high-performance, ephemeral accelerator for stateful operations, such as atomic counters. 1
Elasticsearch: A distributed search and analytics engine for ingesting, storing, and querying structured log data from pipeline executions. 1
Kibana / Custom Frontend: The user interface layer for visualizing data from Elasticsearch, providing dashboards for debugging and observability. 1

### 2.4 API and Application Services

FastAPI (Python): The web framework for building the synchronous RESTful API for environment management. 1
Pydantic: The data validation library used within the FastAPI service to enforce strict schema contracts for API requests and responses. 1

## 3.0 How the Tech Stack Solves the Goals

The technology stack is architected to meet the platform's goals through specific, interconnected patterns.
To enable high-throughput parallel build orchestration, the platform must implement a multi-layered caching strategy. The success of the parallel orchestration system is contingent upon the correct implementation of this granular caching architecture. Dagger's $sharing=dagger.CacheSharingMode.LOCKED$ will be applied to highly granular, content-addressed cache volumes hosted on a shared VFS. This approach transforms the VFS from a single point of contention into a partitioned, content-addressable keystore, which is a prerequisite for minimizing lock conflicts and enabling effective parallel execution. 1
System-wide resilience and data integrity shall be achieved by implementing the Transactional Outbox pattern as the foundational principle for all state changes. The combination of PostgreSQL, Debezium, and Kafka ensures this reliability. All state modifications must first be committed atomically to the PostgreSQL database. Debezium will capture every committed change from the database's Write-Ahead Log and guarantee its publication as an event to Kafka. This architecture is the core mechanism for both build orchestration and environment configuration management, ensuring that the event stream is a perfect, ordered reflection of the committed state. This establishes the database as the source of current state and the Kafka event stream as the immutable, auditable source of truth over time, thereby preserving auditability while offering API-driven convenience. 1
Developer experience will be enhanced through structured logging and proactive failure handling. Dagger logs, enriched with metadata such as build_id, will be structured by an Elasticsearch Ingest Pipeline. This process converts raw text into queryable fields, enabling a rich debugging UI with features like log-to-code traceability. Pipeline reliability is improved through a dedicated, stateful timeout-management service that subscribes to Kafka build events. This service decouples failure detection from the core orchestrator by tracking active builds and publishing a standardized dev.platform.build.completed.v1 event upon timeout. This design allows the system to be highly extensible, as any new monitoring component can signal a build failure by publishing the same standardized event to the build lifecycle topic. 1
Flexibility and auditability will be delivered via a hybrid configuration model that supports two distinct but complementary paradigms: Git-managed static environments and API-managed dynamic environments.
API-Managed Environments: For dynamic, on-demand use cases, the environment-manager-api service provides a synchronous REST API for managing environment state in PostgreSQL. This is ideal for ephemeral developer sandboxes and PR preview environments.
Git-Managed Environments: For static, foundational environments like production and staging, configuration is managed declaratively in a protected Git repository. A new GitOps controller service synchronizes the state from Git to the PostgreSQL database.
Crucially, both workflows converge at the database. The Debezium CDC pipeline captures all state changes, regardless of origin (API or Git), and publishes them to the platform.environments.cdc.v1 Kafka topic. This unified event stream creates a single, immutable, and auditable log of all environment state changes, ensuring that downstream consumers like the Orchestrator can react to any change consistently without needing to know its source. 1

## 4.0 Integration Points

This section specifies the directed data flows between system components.

### 4.1 Build Orchestration Event Flow

Orchestrator to PostgreSQL: The Orchestrator initiates a deployment by writing deployments and builds records (status: PENDING) in a single database transaction.
PostgreSQL (WAL) to Debezium to Kafka: Debezium captures the INSERT operations on the builds table from the WAL and publishes dev.platform.build.task.v1 events to the platform.builds.v1 topic.
Kafka to Builder Services: Ephemeral Builder services consume dev.platform.build.task.v1 events.
Builder to Kafka: Upon starting a build, a Builder publishes a dev.platform.build.started.v1 event. Upon completion, it publishes a dev.platform.build.completed.v1 event.
Kafka to Orchestrator/State Manager: The Orchestrator consumes dev.platform.build.completed.v1 events to update the status of the corresponding builds record in PostgreSQL.
Orchestrator to Redis: For each SUCCEEDED event, the Orchestrator performs an atomic increment on a deployment-specific counter in Redis.
Orchestrator to Kafka: When the Redis counter matches the expected_build_count, the Orchestrator publishes a dev.platform.deployment.ready.v1 event to the platform.deployments.v1 topic.

### 4.2 Environment Management CDC Flow

User/Client to FastAPI Service: A user or client makes a POST, GET, or DELETE request to the /environments endpoint.
FastAPI Service to PostgreSQL: The service validates the request and performs the corresponding INSERT, UPDATE, or DELETE operation on the environments table.
PostgreSQL (WAL) to Debezium to Kafka: Debezium captures the database operation and publishes a corresponding immutable event to the platform.environments.cdc.v1 topic.
Kafka to Orchestrator: The Orchestrator consumes events from this topic to trigger environment creation, update, or teardown workflows.

### 4.3 Observability Data Ingestion Flow

Dagger to Elasticsearch: All log output from Dagger pipeline executions is streamed to an Elasticsearch datastream, annotated with the build_id.
Elasticsearch (Ingest Pipeline): Before indexing, the Ingest Pipeline parses, structures, and enriches the log data with contextual metadata retrieved by referencing the build_id.
Elasticsearch to Kibana/UI: The structured log data is made available for querying and visualization in the debugging interface.

### 4.4 Timeout and Failure Handling Flow

Kafka to Timeout Service: The service consumes dev.platform.build.started.v1 and dev.platform.build.completed.v1 events from the platform.builds.v1 topic.
Timeout Service (Internal State): It maintains an internal, stateful map of active build_ids and their associated timeout timers. 1
Timeout Service to Kafka: If a timer fires for a build_id, the service synthesizes and publishes a dev.platform.build.completed.v1 event with status: FAILED and status_reason: TIMEOUT.

### 4.5 GitOps-Managed Environment Sync Flow

Git Repository to GitOps Controller: A git push to the protected main branch of the static environments repository (following a mandatory PR approval) triggers a webhook to a new GitOps controller service.
GitOps Controller to PostgreSQL: The controller fetches the configuration files from the repository. It then reconciles the state with the environments table, performing INSERT, UPDATE, or DELETE operations as needed. All records it manages are marked with CREATED_BY: "system" and platformTeamId.
PostgreSQL (WAL) to Debezium to Kafka: This flow remains identical to the API-driven path. Debezium captures the database operations from the controller and publishes corresponding events to the platform.environments.cdc.v1 topic.
Kafka to Orchestrator: The Orchestrator consumes events from this topic to trigger environment creation, update, or teardown, just as it does for API-initiated changes.

## 5.0 Contracts

This section provides the formal, canonical definitions for all data structures and interfaces.

### 5.1 Dagger Cache Volume Keying Contract

All Dagger cache volumes must be keyed using the following string format: v1-{service_name}-{cache_type}-{git_ref_slug}-{content_hash}. The components are defined as:
v1: A static version prefix for global cache invalidation.
service_name: The name of the microservice being built.
cache_type: A descriptor for the cache contents (e.g., node-modules, go-build-cache).
git_ref_slug: The sanitized Git branch or tag name.
content_hash: A SHA256 hash of the file(s) determining cache validity (e.g., package-lock.json, go.sum).

### 5.2 PostgreSQL Data Schemas

#### 5.2.1 deployments Table Schema

SQL

CREATE TABLE deployments (
    deployment_id UUID PRIMARY KEY,
    expected_build_count INT NOT NULL CHECK (expected_build_count > 0),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'BUILDING', 'DEPLOYING', 'SUCCEEDED', 'FAILED')),
    creation_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_modified_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

#### 5.2.2 builds Table Schema

SQL

CREATE TABLE builds (
    build_id UUID PRIMARY KEY,
    deployment_id UUID NOT NULL REFERENCES deployments(deployment_id) ON DELETE CASCADE,
    service_name VARCHAR(255) NOT NULL,
    git_ref VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED')),
    status_reason TEXT,
    artifact_url VARCHAR(1024),
    creation_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_modified_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version BIGINT NOT NULL DEFAULT 1,
    UNIQUE(deployment_id, service_name)
);

#### 5.2.3 environments Table Schema

SQL

CREATE TABLE environments (
    environment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    environment_name VARCHAR(255) NOT NULL UNIQUE,
environment_size,
    team_id VARCHAR(255) NOT NULL,
    spec JSONB NOT NULL,
    created_by_user_id VARCHAR(255) NOT NULL,
    last_modified_by_user_id VARCHAR(255) NOT NULL,
    creation_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_modified_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expiration_timestamp TIMESTAMPTZ,
    version BIGINT NOT NULL DEFAULT 1
);
For records managed by the GitOps controller, created_by_user_id will be the literal string "system", and team_id will be platformTeamID.

### 5.3 Kafka Event Schemas

#### 5.3.1 Topic: platform.builds.v1

Event Type: dev.platform.build.task.v1
Source: Debezium
Payload: A Debezium change event envelope containing the full builds row data in the after field.
Event Type: dev.platform.build.started.v1
Source: Builder Service
Payload:
JSON
{
  "build_id": "uuid-string",
  "deployment_id": "uuid-string",
  "start_timestamp": "ISO-8601-string"
}
Event Type: dev.platform.build.completed.v1
Source: Builder Service or Timeout Service
Payload:
JSON
{
  "build_id": "uuid-string",
  "deployment_id": "uuid-string",
  "status": "SUCCEEDED | FAILED",
  "status_reason": "e.g., TIMEOUT, TEST_FAILURE",
  "artifact_url": "oci-url-if-succeeded",
  "end_timestamp": "ISO-8601-string"
}

#### 5.3.2 Topic: platform.deployments.v1

Event Type: dev.platform.deployment.ready.v1
Source: Orchestrator
Payload:
JSON
{
  "deployment_id": "uuid-string",
  "artifacts": [
    { "service_name": "service-a", "artifact_url": "oci-url-a" },
    { "service_name": "service-b", "artifact_url": "oci-url-b" }
  ]
}

#### 5.3.3 Topic: platform.environments.cdc.v1

Event Type: Debezium change event for the environments table. The payload must contain the before and after state of the row, consistent with the Debezium format. 1

### 5.4 environment-manager-api Service Contract

The environment-manager-api service shall expose a RESTful interface with enhanced authorization logic. A global rule must be implemented to reject any write request (POST, PUT, DELETE) targeting an environment where management_type = 'GIT', ensuring these environments are exclusively managed via the GitOps workflow.
The following endpoints are provided for API-managed environments:
POST /environments
Description: Creates a new environment definition. The team_id and created_by_user_id shall be extracted from the authenticated user's token. The expiration_timestamp shall be set automatically for ephemeral environments.
Response: 201 Created with the full environment object.
GET /environments
Description: Lists all environments accessible to the user's team.
Response: 200 OK with an array of environment objects.
GET /environments/{name}
Description: Retrieves the details of a single environment by its unique name, subject to team access controls.
Response: 200 OK with the environment object, 403 Forbidden if not on the correct team, or 404 Not Found.
PUT /environments/{name}
Description: Updates an existing environment definition. Authorization is granted if the user is the creator of the record (created_by_user_id) or if the user has a team admin role for the record's team_id.
Response: 200 OK with the updated environment object, 403 Forbidden if unauthorized, or 404 Not Found.
DELETE /environments/{name}
Description: Deletes an environment definition. Authorization is granted based on the same rules as PUT: the user must be the creator or a team admin.
Response: 204 No Content on success, 403 Forbidden if unauthorized, or 404 Not Found.
All write operations must implement optimistic locking by checking and incrementing the version field in the environments table. 1 Pydantic models must be used for all request and response validation. 1

## 6.0 Workflows

This section specifies the step-by-step logic for key system processes.

### 6.1 Parallel Build Orchestration Workflow

Initiation: A deployment request triggers the Dagger Orchestrator pipeline.
State Registration: The Orchestrator creates a deployments record and one builds record per artifact in PostgreSQL. The builds records are created with a status of PENDING.
Event Publication: Debezium captures the INSERT operations and publishes a dev.platform.build.task.v1 event to Kafka for each new builds record.
Parallel Execution: Ephemeral Builder services consume these tasks. A Builder immediately publishes a dev.platform.build.started.v1 event, executes the Dagger pipeline, and upon completion, publishes a dev.platform.build.completed.v1 event with the final status and artifact URL.
State Aggregation: The Orchestrator consumes completed events and updates the status in the builds table in PostgreSQL.
Deployment Trigger: The Orchestrator uses a Redis counter, incremented for each SUCCEEDED build. When the counter equals the expected_build_count, it publishes a dev.platform.deployment.ready.v1 event to trigger the final deployment phase.

### 6.2 Event-Driven Timeout Handling Workflow

Subscription: A dedicated timeout-management service subscribes to the platform.builds.v1 Kafka topic.
Stateful Tracking: Upon consuming a dev.platform.build.started.v1 event, the service adds the build_id to an internal state store and schedules a cancellation timer for 30 minutes.
Completion Handling: If a dev.platform.build.completed.v1 event is received for that build_id, the service cancels the associated timer and removes the entry from its state store.
Timeout Execution: If the 30-minute timer fires, the service synthesizes and publishes a new dev.platform.build.completed.v1 event to Kafka with its status set to FAILED and status_reason set to TIMEOUT.

### 6.3 API-Driven Environment Management Workflow

API Interaction: A user interacts with the environment-manager-api service to create, modify, or delete an environment definition. The service enforces authorization checks to ensure users can only manipulate records they created or that belong to their team if they are a team admin.
Database Transaction: The API service performs the corresponding INSERT, UPDATE, or DELETE operation on the environments table in PostgreSQL within a single transaction.
Change Data Capture: A Debezium connector, monitoring the environments table, captures the committed change from the database's WAL.
Event Publication: Debezium publishes a structured, immutable event representing the change to the platform.environments.cdc.v1 Kafka topic. This topic serves as the authoritative, auditable log of all environment state changes.
Orchestrator Consumption: The Dagger Orchestrator consumes events from this topic. An INSERT event triggers environment creation, an UPDATE triggers an update, and a DELETE event triggers the teardown workflow.

### 6.4 GitOps-Driven Static Environment Management Workflow

Change Initiation and Approval: A platform engineer clones the static environments Git repository, creates a new branch, and modifies or adds a JSON configuration file. The change is submitted as a Pull Request (PR).
Peer Review and Merge: A designated approver reviews the PR. Upon approval, the PR is merged into the protected main branch.
Synchronization: The merge event triggers a GitOps controller. The controller fetches the latest configuration from Git and reconciles the state with the environments table in PostgreSQL. It creates, updates, or deletes records as necessary, marking them with management_type: 'GIT', created_by_user_id: 'system', and the platform team's ID.
Change Data Capture and Orchestration: This step mirrors the API workflow. Debezium captures the transaction from the database WAL, publishes an event to platform.environments.cdc.v1, and the Orchestrator consumes this event to apply the changes, ensuring a consistent and unified orchestration process.

## 7.0 Use Cases

This section defines the functional capabilities of the platform.
High-Concurrency, Cache-Accelerated Service Builds: The system shall execute multiple, concurrent Dagger builds for different services and branches. It will leverage granular, content-addressed caching with the key format v1-{service_name}-{cache_type}-{git_ref_slug}-{content_hash} and $sharing=dagger.CacheSharingMode.LOCKED$ to minimize build times and prevent lock contention.
Fault-Tolerant Multi-Service Deployments: The system shall orchestrate the build of all services required for a deployment. It must tolerate the failure and restart of individual builder instances and only trigger the final deployment process once all required artifacts have been successfully built, as tracked via events and the PostgreSQL state store.
Rapid Test Failure Diagnosis and Debugging: A developer shall be able to view a Gantt-style chart of a deployment's builds, identify a failed test, and navigate via a hyperlink to the exact, pre-filtered log lines for that test failure from the specific build run. The UI will also provide a direct link to the source code at the specific commit (git_ref) that was tested.
Proactive Timeout Detection: The system shall automatically detect and fail any build that runs longer than the configured 30-minute timeout period. This failure will be reported through the standard dev.platform.build.completed.v1 event, ensuring consistent handling by the orchestrator.
API-Based Ephemeral Environment Provisioning: A user or automated tool shall be able to provision a new, temporary environment by making a single POST request to the /environments endpoint. The system will automatically trigger the creation workflow and record the action in the auditable platform.environments.cdc.v1 event log. The environment will be subject to automated cleanup based on its expiration_timestamp.
Version-Controlled Management of Production Environments: A platform operator needs to update the network policy for the production environment. They submit a Pull Request with the change to the production.json file in the protected Git repository. After a mandatory peer review and approval, the change is merged and automatically synchronized to the platform by the GitOps controller, providing a fully audited and version-controlled change management process for critical infrastructure.
