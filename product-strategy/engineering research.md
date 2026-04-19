# Engineering Research: Technical Landscape

## Codebase Catalog

### API Service (`services/api/`)

**Contracts:**
- `app/contracts/base.py`: `VersionedMixin` still exists as a generic non-negative `version` field mixin, even though the live chapter API has already moved to `ETag`/`If-Match`.
- `app/contracts/activity.py`: `ActionStatus`, `ActionRecord`, `StateChangeRecord`, and `AggregateHead` model the append-only activity/audit pattern from `plans/research/activity-audit-model.md`.
- `app/contracts/chapters.py`: `ChapterStatus`, `ChapterCreate`, `ChapterRead`, and `ChapterUpdate` define chapter CRUD shapes. The current contract body has no `version` field; concurrency is header-based.

**Repositories:**
- `app/repositories/activity.py`: `InMemoryActionStore` and `InMemoryStateChangeStore` append accepted/rejected action records and per-aggregate state changes. They are in-memory only.
- `app/repositories/chapters.py`: `ChapterRepository` protocol plus `InMemoryChapterRepository` implement `create`, `list`, `get`, `update`, and `archive` over an in-memory dict. No SQL/Postgres repository exists.

**Services:**
- `app/services/chapters.py`: `ChapterService` wraps chapter mutations, computes diffs, appends activity/state-change records, tracks aggregate heads in memory, and returns `ETag` values for optimistic locking.

**Endpoints:**
- `GET /api/v1/health`: returns service name and version from `app.state.settings`.
- `POST /api/v1/chapters`: creates a chapter, defaults it to `provisioning`, appends activity/state-change records, and returns an `ETag`.
- `GET /api/v1/chapters`: lists all in-memory chapters.
- `GET /api/v1/chapters/{chapter_id}`: returns a single chapter plus its current `ETag`.
- `PATCH /api/v1/chapters/{chapter_id}`: requires `If-Match`, updates chapter business fields, and returns `412` on stale preconditions and `428` when the header is missing.
- `POST /api/v1/chapters/{chapter_id}/archive`: requires `If-Match`, archives the chapter, and advances the aggregate head.

**Tests:**
- `services/api/tests/test_activity_model.py` (`56` tests): the strongest current API-spec file. It covers append-only activity contracts, header-based optimistic locking, chapter `ETag` flows, and action/state-change recording.
- `services/api/tests/test_chapters.py` (`22` tests): older chapter CRUD tests that still expect body `version` fields and `409` conflicts; these no longer match the implementation.
- `services/api/tests/test_contracts_base.py` (`15` tests): still validates `VersionedMixin` and body-version optimistic locking examples.
- `services/api/tests/test_contracts_chapters.py` (`18` tests): still expects `ChapterRead` and `ChapterUpdate` to inherit `VersionedMixin`.
- `services/api/tests/test_endpoints_chapters_stubs.py` (`3` tests): older stub-route tests that expect `501`/`not implemented` style behavior, also stale relative to the live endpoints.
- `services/api/tests/test_factory.py` (`8` tests): factory wiring and settings usage.
- `services/api/tests/test_settings.py` (`17` tests): env-var parsing and redaction.
- `services/api/tests/test_conftest.py` (`6` tests): FastAPI fixture coverage.

**Factory/settings/middleware structure:**
- `app/core/factory.py` creates the FastAPI app, constructs in-memory repositories/stores by default, and places the `ChapterService` plus settings on `app.state`.
- `app/core/dependencies.py` exposes the `ChapterService` through `Depends`.
- `app/core/settings.py` defines app metadata plus env contracts for Discord, Supabase, Google Vision, Gemini, Z AI, and Minimax keys.
- There is no middleware layer yet for auth, actor context, correlation IDs, request logging, or shared error translation.

**Architecture patterns:**
- The service follows the intended layered shape `api -> services -> repositories -> infrastructure`, but only the chapter aggregate is wired through it.
- `app/infrastructure/` exists only as an empty package marker. No Supabase/Postgres client, no OCR client, and no external provider adapters are implemented.
- Persistence is entirely in-memory in the canonical API service. There is no durable database backing the current FastAPI code.

### Discord Daemon (`services/discord/`, plus preserved legacy `daemon/`)

**Current canonical service shell (`services/discord/`):**
- `services/discord/app/__main__.py`: async process entry point. It loads env settings, configures Discord logging, registers a SIGTERM shutdown handler, starts `HumilityBot`, and closes cleanly on exit paths.
- `services/discord/app/core/bot.py`: defines `HumilityBot` as a `commands.Bot` with `members=True`, `message_content=True`, and `presences=False`.
- `services/discord/app/core/settings.py`: env-backed settings for `discord_bot_token`, `discord_guild_id`, and `supabase_db_url`.
- `services/discord/app/commands/`, `handlers/`, and `tasks/`: empty package placeholders. No slash commands, event handlers, background jobs, or API clients are implemented yet.
- `services/discord/tests/test_bot.py` (`8` tests), `test_main.py` (`8` tests), and `test_settings.py` (`7` tests) validate only startup/settings behavior.

**Preserved pre-research draft daemon (`daemon/`):**
- `daemon/__main__.py`: draft runtime entry. It loads `.env`, parses `chapters.yaml`, opens a SQLite database, creates a `HumilityBot`, registers `/ping`, calls `setup_applications()`, and syncs guild commands.
- `daemon/config.py`: YAML config loader for `chapters.yaml` and `forms/*.yaml`. It validates chapter wiring, question types, option limits, and chunks form steps into `modal` and `followup_selects` groups of at most five questions.
- `daemon/db.py`: SQLite bootstrap and CRUD helpers. It creates four tables: `chapters`, `submissions`, `tickets`, and `chapter_blacklist`. It includes helpers for submission status transitions and active-submission lookups.
- `daemon/claim.py`: private-thread membership helpers used for claim visibility. It preserves requester/claimer/admin/bot visibility and explicitly rejects public threads.
- `daemon/applications.py`: the only substantive interaction draft. It defines `/apply`, modal session state, persistent review buttons (`Claim`, `Interview`, `Approve`, `Deny`), blacklist checks, active-submission checks, and submission-status transitions. It does not implement canonical API calls, still uses direct SQLite helpers, and its modal-completion path stops at an ephemeral "draft recorded" response rather than a full canonical submission write.

**Interactions currently implemented:**
- New canonical daemon: none.
- Legacy draft daemon: `/ping`, `/apply`, application review buttons, and thread-claim visibility helpers.

**Configuration currently loaded:**
- New canonical daemon: environment only.
- Legacy draft daemon: environment plus `chapters.yaml` and per-chapter YAML form definitions.

**Database operations currently present:**
- New canonical daemon: none.
- Legacy draft daemon: SQLite CRUD for chapters, submissions, tickets, blacklist entries, and private-thread claim/member adjustments.

**Tests for preserved draft runtime:**
- `tests/test_daemon_init.py` (`5` tests): package contract.
- `tests/test_daemon_entry.py` (`8` tests): entrypoint/env/database wiring.
- `tests/test_daemon_config.py` (`17` tests): YAML schema validation and form-step chunking.
- `tests/test_daemon_db.py` (`9` tests): SQLite schema and CRUD helpers.
- `tests/test_daemon_claim.py` (`6` tests): private-thread visibility semantics.
- `tests/test_daemon_applications.py` (`8` tests): modal/view contract only.
- `tests/test_discord_cli.py` (`55` tests): read-only gateway CLI serialization and command surface.

### Infrastructure (`infra/`, `k8s/`)

**OpenTofu modules and environments (`infra/`):**
- `infra/bootstrap/state-backend/main.tf`: one-time Vultr Object Storage bootstrap for OpenTofu remote state.
- `infra/modules/platform-network/main.tf`: per-environment Vultr VPC module.
- `infra/modules/platform-cluster/main.tf`: per-environment Vultr Kubernetes Engine cluster module exposing `cluster_id`, `endpoint`, `kube_config`, and `firewall_group_id`.
- `infra/environments/dev/main.tf`: persistent dev root in `ewr`, `10.40.0.0/20`, `2` nodes.
- `infra/environments/staging/main.tf`: on-demand staging root in `ewr`, `10.40.16.0/20`, `3` nodes.
- `infra/environments/production/main.tf`: persistent production root in `ewr`, `10.40.32.0/20`, `3` nodes.
- `infra/environments/*/backend.tfbackend`: remote-state config files still contain `REPLACE_AFTER_BOOTSTRAP` placeholders, so the bootstrap handoff is not finalized in-repo.
- `infra/tests/validate_platform_bootstrap.sh`: shell acceptance checks for file presence, formatting, provider pinning, and basic root/module structure.

**Kubernetes manifests (`k8s/`):**
- `k8s/base/`: environment-neutral Kustomize base for namespaces, policy/config `ConfigMap`s, and controller-contract metadata.
- `k8s/overlays/{dev,staging,production}/{app-cluster,control-cluster}/kustomization.yaml`: per-environment, per-role overlays referencing `base/`.
- `k8s/clusters/{dev,staging,production}/{app-cluster,control-cluster}/`: Flux `GitRepository` and `Kustomization` roots for each cluster role.
- `k8s/clusters/*/app-cluster/manifests/bootstrap/`: empty topology slots for future bootstrap/workload resources.
- `k8s/clusters/*/control-cluster/manifests/claims/`: empty topology slots for future Crossplane claims.
- `k8s/tests/test_gitops_foundation.sh`: shell acceptance checks for layering, Flux scoping, and cluster-root boundaries.

**Deployment pipeline state:**
- Infrastructure and GitOps foundations exist as repo artifacts, but there are no application workload manifests, no image automation, and no Buildkite pipeline files in the repo.
- The Flux roots still point at placeholder Git URLs (`ssh://git@example.com/humility/discord.git`), so cluster reconciliation is scaffolded rather than live.
- The infra tree is Vultr-specific, while `plans/platform-decisions-overlay.md` still records `Hetzner vs Vultr` as open. The repo implementation is therefore ahead of a fully locked hosting decision.

### Migrations

- There is no `migrations/` directory and no Alembic configuration anywhere in the repo.
- The canonical FastAPI service has no durable schema at all; its repositories are in-memory.
- The only concrete schema in the repo is the legacy SQLite schema embedded in `daemon/db.py`, with tables `chapters`, `submissions`, `tickets`, and `chapter_blacklist`.
- Current schema state for the intended cloud architecture is therefore effectively `not started`.

### Other Repository Directories

- `product-strategy/`: problem framing, philosophy, approved proposal, and approved executive roadmap.
- `plans/research/`: post-research artifacts for `activity-audit-model`, `platform-bootstrap`, and `gitops-foundation`.
- `research/`, `proposals/`, `risk/`: earlier numbered phase outputs for the legacy daemon/API work and other small slices.
- `docs/` and `forms/`: preserved draft design and intake artifacts.
- `tests/`: top-level tests for preserved draft runtime and the read-only `discord_cli.py`.
- `.tmp/`: agent scratch prompts and prior review artifacts; not runtime code.
- `apps/`, `packages/`, and `migrations/` from the target architecture described in `AGENTS.md` do not exist yet.

### Draft-State Artifacts

- Per `DECISIONS.md` D3, the preserved pre-research draft artifacts are `daemon/`, `forms/`, `docs/DAEMON_DESIGN.md`, and `docs/APPLICATIONS_SKETCH.md`. These are explicitly kept for hookpoint comparison and are not approved architecture.
- Per `DECISIONS.md` D2, the SQLite-backed daemon code is historical only. Any logic that depends on `daemon/db.py` or direct SQLite state is draft-state, not canonical.
- `chapters.yaml` is an empty draft registry meant for the old daemon flow; it is not the approved canonical chapter model.
- `discord_cli.py` remains a supported inspection surface from D1, but it is read-only tooling, not the future mutation architecture.
- `services/api/`, `services/discord/`, `infra/`, and `k8s/` are not D3 draft-state. They are post-research scaffolds, but they are still incomplete: in-memory persistence, empty bot command packages, no workload manifests, and no migration layer.

## Initiative Mapping

### VS-101: Screen Newcomers With a Durable Trust Dossier

**What exists:** Generic activity/audit contracts and stores in `services/api/app/contracts/activity.py` and `services/api/app/repositories/activity.py`; API and Discord process shells; `discord_cli.py` can inspect members and roles read-only.
**What is reusable:** The append-only action/state-change model, the FastAPI factory/dependency pattern, and the Discord runtime shell.
**What is draft-state:** No direct trust-dossier implementation exists in D3 draft artifacts.
**What is missing:** `Member`, `TrustProfile`, `TrustSignal`, `TrustComputationConfig`, `AuditEntry`, trust recomputation logic, reviewer inspection endpoints, canonical persistence, and Discord/UI review surfaces.
**Locked decision constraints:** `D1` research-first workflow; `D2` no SQLite/local-first canonical architecture.
**Schema constraints:** Greenfield canonical tables. There is no existing approved trust schema to alter.
**Discord API constraints:** Any Discord-native review surface will still be subject to interaction timeouts, message-component limits, and rate limits.
**External dependencies:** None are currently locked for trust computation.
**Testing requirements:** New API contract tests, trust-computation fixtures, and reviewer-surface integration tests. No current tests cover this domain.

### VS-102: Claim and Review Applications Without Reviewer Collisions

**What exists:** `daemon/applications.py` implements `/apply`, modal session state, review buttons, blacklist checks, and draft claim/interview status transitions, but the modal-completion path still stops short of a full submission write; `daemon/db.py` provides `submissions` storage helpers; `daemon/config.py` loads YAML forms; `forms/dark-nemesis.yaml` is a real form example.
**What is reusable:** The form-question model and step-chunking rules from `daemon/config.py`; private-thread claim visibility from `daemon/claim.py`; the action/state-change pattern from the new API scaffold.
**What is draft-state:** All current application behavior is in D3-preserved `daemon/` and `forms/` code, and it depends on rejected SQLite persistence.
**What is missing:** Canonical `FormDefinition`, `Application`, `ApplicationReview`, and `AuthorityGrant` models; networked persistence; reviewer queue routing; exclusive claim handling in the canonical API; trust-context integration; and new `services/discord` handlers.
**Locked decision constraints:** `D2` rejects SQLite as canonical storage; `D4` locks full application review as the chapter-intake default; `D6` preserves waitlist as a pre-decision holding pattern.
**Schema constraints:** The legacy `submissions` table is draft-only. Canonical application tables are still greenfield.
**Discord API constraints:** Modal inputs are capped at five per step and select menus at twenty-five options; the draft loader already chunks around those platform limits.
**External dependencies:** None beyond Discord.
**Testing requirements:** Separate contract-first tests for exclusive claim behavior and reviewer collisions, plus Discord interaction tests. Current tests only validate draft modal/view shapes.

### VS-103: Decide Applications With Interviews, Waitlists, and Reasons

**What exists:** Draft application review buttons already transition to `interview`, `approved`, and `denied` statuses in SQLite.
**What is reusable:** Draft status names and review-action affordances; the API activity/audit pattern for reconstructable decisions.
**What is draft-state:** The entire current application-decision path is legacy `daemon/` + SQLite.
**What is missing:** Waitlist state, reason capture, `NotificationRule`, canonical audit linkage, interview-surface management in the new daemon, and API-side decision endpoints.
**Locked decision constraints:** `D4` requires waitlists; `D6` defines waitlist semantics as pre-decision, not approval.
**Schema constraints:** New canonical application-decision tables are required; altering the draft SQLite table would not satisfy `D2`.
**Discord API constraints:** Private interview flows and review actions must fit Discord thread/channel limits and interaction timing rules.
**External dependencies:** None beyond Discord.
**Testing requirements:** Full application state-machine tests, notification tests, and decision-rationale persistence tests.

### VS-201: Open and Assign Private Cases in the Right Queue

**What exists:** `daemon/db.py` defines a draft `tickets` table; `daemon/claim.py` implements private-thread membership narrowing/preservation; `docs/DAEMON_DESIGN.md` documents a queue-message-plus-private-thread ticket model.
**What is reusable:** The private-thread claim helper and its tests; the general thread-based routing concept as historical input.
**What is draft-state:** The ticket table and queue/thread model are preserved pre-research drafts.
**What is missing:** `TicketCategory`, `Ticket`, `TicketMessage`, `TicketTransition`, privacy/routing logic, canonical persistence, queue assignment surfaces, and all new-daemon handlers.
**Locked decision constraints:** `D2` blocks SQLite as canonical persistence.
**Schema constraints:** Ticket/case-management schema is greenfield in the canonical architecture.
**Discord API constraints:** The current claim helper only supports private threads; this is compatible with Discord channel-cap constraints but forbids public-thread workflows.
**External dependencies:** None.
**Testing requirements:** Discord thread-membership tests, category routing tests, and API state-machine tests. Current coverage only touches legacy claim visibility and draft table CRUD.

### VS-202: Enforce Category-Specific Escalation and Accountability

**What exists:** No runtime implementation. The legacy `tickets` table has only a single `status` column and no category-specific workflow data.
**What is reusable:** The action/state-change audit pattern and the private-thread claim helper.
**What is draft-state:** The existing ticket schema is too shallow for SLA/escalation and remains draft-state.
**What is missing:** `TicketCategory`, SLA rules, per-category state machines, escalation/resolution reasons, notifications, background jobs, and canonical persistence.
**Locked decision constraints:** `D1` research-first; `D2` no SQLite canonical path.
**Schema constraints:** Entirely new canonical ticket-category and transition tables are needed.
**Discord API constraints:** Notifications and escalations must operate within Discord rate limits and thread/channel capabilities.
**External dependencies:** None.
**Testing requirements:** Time-based escalation tests, notification tests, and per-category transition tests. No existing scheduler/task framework exists in `services/discord/app/tasks/`.

### VS-301: Provision Chapters From Templates

**What exists:** The post-research chapter API implements create/list/get/update/archive with `ETag` concurrency and append-only activity records; the legacy daemon holds draft chapter YAML/SQLite wiring and template-clone design notes.
**What is reusable:** `services/api/app/contracts/chapters.py`, `services/api/app/services/chapters.py`, `services/api/app/api/v1/endpoints/chapters.py`, and the activity stores; the empty `chapters.yaml` and old design docs are usable as hookpoint references only.
**What is draft-state:** `daemon/db.py` chapter table, `chapters.yaml`, and `docs/DAEMON_DESIGN.md` provisioning sequence.
**What is missing:** `ChapterTemplate`, `ChapterTransition`, `PermissionIntent`, `PolicyVersion`, durable repositories, actual Discord provisioning logic, and any new-daemon command/handler implementation.
**Locked decision constraints:** `D4` makes chapter provisioning a first-class MVP subsystem; `D2` blocks the old SQLite path.
**Schema constraints:** The current canonical chapter model is in-memory only. Durable chapter and permission-intent tables do not exist yet.
**Discord API constraints:** Template cloning is bounded by Discord role, channel, and category caps called out in the proposal.
**External dependencies:** None beyond Discord and eventual database storage.
**Testing requirements:** API optimistic-locking tests already exist, but provisioning needs Discord integration tests, dry-run validation, and durable repository tests.

### VS-302: Keep Chapter Rosters and Leadership Transitions Coherent

**What exists:** No direct roster or succession code exists. Only generic chapter CRUD scaffolding is present.
**What is reusable:** The chapter API skeleton and append-only activity model.
**What is draft-state:** There is no dedicated D3 roster implementation to salvage.
**What is missing:** `ChapterRole`, `RosterEntry`, `RosterTransition`, `AuthorityGrant`, leadership-transfer workflows, Discord role-sync logic, and canonical persistence.
**Locked decision constraints:** `D4` makes chapter operations first-class; `D2` still rules out SQLite as the canonical data path.
**Schema constraints:** Entirely new roster and authority tables are required.
**Discord API constraints:** Leadership turnover ultimately touches live role grants and permission overwrites.
**External dependencies:** None.
**Testing requirements:** Transition/audit tests plus Discord role-sync mocks. No current tests cover roster state.

### VS-401: Evaluate Chapter Compliance From Evidence Instead of Spreadsheets

**What exists:** The repo has post-research activity/audit contracts and in-memory stores, plus API settings placeholders for `google_cloud_vision_key` and `gemini_api_key`. No compliance-specific models or OCR adapters exist.
**What is reusable:** The append-only action/state-change model, chapter API skeleton, and env contracts for the locked OCR providers.
**What is draft-state:** This subsystem does not appear in the preserved D3 draft code.
**What is missing:** `ComplianceRule`, `EvidenceSubmission`, `ComplianceEvaluation`, evidence storage, OCR ingestion, scheduled evaluation, chapter-rule configuration, roster linkage, and officer review surfaces.
**Locked decision constraints:** `D5` makes activity tracking a primary requirement; `D6` locks Google Cloud Vision as primary OCR and Gemini as fallback.
**Schema constraints:** Compliance/evidence tables are greenfield in the canonical architecture.
**Discord API constraints:** Screenshot submission and review flows must work within Discord attachment handling and interaction limits.
**External dependencies:** Google Cloud Vision and Gemini are locked dependencies for this initiative.
**Testing requirements:** OCR adapter mocks, evidence-submission fixtures, rule-evaluation tests, and integration tests across evaluation and chapter/roster context.

### VS-402: Apply Graduated Compliance Consequences With Officer Review

**What exists:** No direct implementation.
**What is reusable:** The same activity/audit scaffolding that VS-401 can build on.
**What is draft-state:** None.
**What is missing:** Consequence routing, roster-transition automation, officer override flows, audit linkage across evaluation and consequence handling, and notification plumbing.
**Locked decision constraints:** `D5` and `D6` apply here as well.
**Schema constraints:** Depends on new compliance and roster schemas; there is no existing canonical table to alter.
**Discord API constraints:** Consequence notifications and officer review actions will be subject to Discord rate limits and UI constraints.
**External dependencies:** Google Cloud Vision and Gemini through the upstream compliance-evaluation path.
**Testing requirements:** Consequence-engine tests, override-path tests, and roster-transition integration tests.

### VS-501: Detect Permission Drift Against Declared Intent

**What exists:** No Discord permission-management runtime code exists. The nearest reusable concept is the desired-state/reconciliation posture in `infra/` and `k8s/`, plus the FastAPI `ETag`/activity patterns.
**What is reusable:** The activity/audit pattern, optimistic-locking approach, and the infra repo's desired-vs-actual mindset.
**What is draft-state:** No preserved D3 permission-drift implementation exists.
**What is missing:** `PermissionIntent`, `PermissionDrift`, `AuthorityGrant`, drift snapshotting, Discord permission readers, reporting endpoints, and daemon-side inspection/reconciliation surfaces.
**Locked decision constraints:** `D1` research-first; `D2` no SQLite canonical path.
**Schema constraints:** All permission-intent and drift tables are greenfield.
**Discord API constraints:** Permission drift requires reliable reads across roles, channels, and overwrites under Discord rate limits.
**External dependencies:** None beyond Discord.
**Testing requirements:** Synthetic guild/channel/role permission fixtures and deterministic diff tests.

### VS-502: Resolve Drift With Reconcile, Accept, or Acknowledge

**What exists:** No implementation beyond the absence above.
**What is reusable:** The API's explicit concurrency and audit patterns.
**What is draft-state:** None.
**What is missing:** Drift-resolution state machine, reconcile/apply flows, acceptance/acknowledgement records, notifications, and authority checks.
**Locked decision constraints:** `D1` research-first; live permission mutations will also be governed operationally by the Mutation Safety workflow in `AGENTS.md`.
**Schema constraints:** Depends on the missing `PermissionIntent` and `PermissionDrift` foundations.
**Discord API constraints:** Reconcile operations are live Discord mutations and therefore inherit rate-limit and permission-overwrite complexity.
**External dependencies:** None beyond Discord.
**Testing requirements:** Permission-diff fixtures plus mutation mocks for reconcile/accept/acknowledge flows.

### VS-601: Change Live Policy Safely With Previews and Concurrency Checks

**What exists:** The chapter API is already a proof-of-concept for header-based optimistic locking with `ETag`/`If-Match`, plus append-only action/state-change recording and diff generation.
**What is reusable:** `services/api/app/services/chapters.py`, `services/api/app/api/v1/endpoints/chapters.py`, `services/api/app/contracts/activity.py`, and the in-memory action/state-change stores.
**What is draft-state:** None of the current policy/concurrency scaffold is in D3 draft-state.
**What is missing:** `PolicyVersion`, preview/diff APIs across subsystems, notification grouping, durable persistence, and subsystem-specific policy editors.
**Locked decision constraints:** `D1` research-first. The policy mechanism must also preserve the proposal's cross-subsystem versioning and reconstructability goals.
**Schema constraints:** The current proof-of-concept is in-memory and chapter-specific. Durable policy-version tables do not exist.
**Discord API constraints:** Policy-change side effects that surface inside Discord still need to respect rate limits and avoid redundant notification floods.
**External dependencies:** None directly, though downstream policy targets may invoke provider-specific services.
**Testing requirements:** Optimistic-locking tests exist for the chapter proof-of-concept; policy preview/version-chain tests and grouped-notification tests do not.

## Shared Infrastructure Needs

| Infrastructure | Needed by | Currently exists? |
|---|---|---|
| Canonical relational persistence plus migrations/Alembic | VS-101, VS-102, VS-103, VS-201, VS-202, VS-301, VS-302, VS-401, VS-402, VS-501, VS-502, VS-601 | No |
| Member, authority, and durable audit foundations (`Member`, `AuthorityGrant`, `AuditEntry`) | VS-101, VS-102, VS-103, VS-201, VS-202, VS-302, VS-501, VS-502, VS-601 | Partial |
| Header-based optimistic locking and policy-versioning primitives | VS-301, VS-501, VS-502, VS-601, plus configuration-heavy parts of VS-101 and VS-401 | Partial |
| Discord interaction framework in `services/discord` (commands, handlers, tasks, API client wiring) | VS-101, VS-102, VS-103, VS-201, VS-202, VS-301, VS-302, VS-401, VS-402, VS-501, VS-502, VS-601 | Partial |
| Form/evidence input modeling and attachment handling | VS-102, VS-103, VS-401, VS-402 | Partial |
| Notification/event dispatch and background scheduling | VS-103, VS-202, VS-302, VS-402, VS-502, VS-601 | No |
| Permission intent and Discord-sync/reconciliation engine | VS-301, VS-302, VS-501, VS-502, VS-601 | No |
| OCR adapters and evidence-processing pipeline | VS-401, VS-402 | No |
| API/Discord test fixtures and service-specific dependency bootstrap | All initiatives | Partial |
| Deployment substrate for running real services | All initiatives | Partial |

## Parallelization Analysis

| Initiative A | Initiative B | Parallelizable? | Reason |
|---|---|---|---|
| VS-201 | VS-501 | Partial | Different product domains, but both need the same missing authority/audit foundations and the same new Discord service shell. |
| VS-201 | VS-601 | Partial | Case workflows and policy versioning are separate features, but both touch shared optimistic-locking, audit, and notification primitives. |
| VS-201 | VS-301 | Partial | Ticket queues and chapter provisioning use different domain models, but both need Discord mutation runtime, authority checks, and audit plumbing. |
| VS-201 | VS-101 | Partial | The domain tables can stay separate, but both require shared member identity and audit foundations that do not exist yet. |
| VS-501 | VS-601 | No | Both center on the same governance surface: `PermissionIntent`, `PolicyVersion`, and safe live mutation semantics. |
| VS-501 | VS-301 | No | Chapter provisioning and permission-drift detection both need `PermissionIntent` and the same Discord permission snapshot/reconciliation layer. |
| VS-501 | VS-101 | Partial | The business logic is separate, but both need shared member/authority/audit infrastructure. |
| VS-601 | VS-301 | No | Chapter provisioning already names `PermissionIntent` and `PolicyVersion`, so the safe-policy-editing mechanism and chapter provisioning will converge on the same tables and endpoints. |
| VS-601 | VS-101 | Partial | Trust-configuration editing can consume a generic policy/versioning layer, but the underlying trust domain can still be built in parallel if the shared policy contract is fixed first. |
| VS-301 | VS-101 | Partial | The main overlap is shared member/audit/authority plumbing, not business tables. |
| VS-102 | VS-202 | Partial | Application claims and case escalation are separate domains, but they both need claim/ownership patterns, notifications, and shared Discord runtime infrastructure. |
| VS-102 | VS-502 | Yes | After shared authority/audit foundations exist, the application-review and permission-resolution domains can mostly proceed on separate schemas and endpoints. |
| VS-102 | VS-302 | Partial | Application review and roster/leadership changes are separate, but both touch authority grants and chapter/member context. |
| VS-202 | VS-502 | Partial | Different workflows, but both need shared authority, notifications, audit, and live Discord mutation safety. |
| VS-202 | VS-302 | Yes | Ticket escalation and chapter roster management can mostly isolate to different domain tables once shared member/authority primitives are in place. |
| VS-502 | VS-302 | Partial | Permission resolution and roster transitions both touch live Discord role/permission state and likely share authority surfaces. |
| VS-103 | VS-401 | Partial | Application adjudication and compliance evaluation use different core data, but both depend on shared notification/audit foundations and chapter/member context. |

## Technical Constraints Summary

- The canonical app architecture is split between post-research scaffolds and preserved pre-research behavior. `services/api/` and `services/discord/` reflect the intended architecture; most feature behavior still lives in D3-preserved `daemon/`, `forms/`, and `docs/`.
- Canonical persistence is missing. There is no migration layer, no durable repository implementation, and no approved relational schema for the cloud-hosted architecture. The only concrete schema is legacy SQLite, which `D2` explicitly demotes to historical draft-state.
- The API test surface is internally inconsistent. `services/api/tests/test_activity_model.py` encodes the current `ETag`/`If-Match` model, while `test_chapters.py`, `test_contracts_base.py`, `test_contracts_chapters.py`, and `test_endpoints_chapters_stubs.py` still assert removed `version`-body and stub-route behavior.
- The workspace is not bootstrapped as a single installable monorepo. Root `pyproject.toml` only packages `discord_cli.py` and `daemon/`; service-specific dependencies live in separate `services/api/pyproject.toml` and `services/discord/pyproject.toml`. A baseline `pytest services/api/tests services/discord/tests tests -q` currently fails immediately with `ModuleNotFoundError: pydantic_settings`.
- The Discord runtime shell is mostly empty in the canonical path. `services/discord/app/commands`, `handlers`, and `tasks` are placeholders, so every roadmap slice that needs live Discord interaction must either port or replace preserved draft logic.
- The target architecture in `AGENTS.md` names `apps/web/`, `packages/shared-types/`, and `migrations/`, but none of those directories exist. Any initiative that expects a web admin surface, generated shared types, or Alembic migrations starts from zero.
- Infrastructure foundations exist, but workload deployment does not. `infra/` and `k8s/` create Terraform/Flux topology, yet the repo has no application Deployments, Services, ingress objects, image build pipeline, or non-placeholder Flux source URLs.
- Hosting is not fully settled at the decision-log level. The repo's infra implementation is Vultr-specific, but `plans/platform-decisions-overlay.md` still records `Hetzner vs Vultr` as open.
- Discord platform limits matter materially for several initiatives: modal inputs cap at five per modal, select options cap at twenty-five, and the proposal explicitly calls out role/channel/category limits and rate limits as hard external constraints.
- OCR/compliance work has locked provider constraints from `D6`: Google Cloud Vision is the primary OCR path and Gemini is the fallback path. Those env vars exist in API settings, but no provider adapter code exists yet.
