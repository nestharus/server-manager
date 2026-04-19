# AI-Optimized Roadmap

## Pipeline Reference

Each work unit is one full `AGENTS.md` implementation pass:

1. Problem research with `gpt-high` and a human scope gate
2. Needs synthesis in this session with a human fit gate
3. Proposal with `gpt-high`
4. Risk gate with `claude-opus` x3 until all risks are LOW
5. Hookpoint research with `gpt-high` and a human gate on surviving code
6. Implementation with test and code agent separation
7. CodeRabbit until clean
8. PR review for decomposition and justification

Pipeline labels used below:

- `Deep`: full research and hookpoint work are expected
- `Standard`: lightweight research plus the normal proposal, risk, hookpoint, test/code, CodeRabbit, and PR review stages

Test boundary rule used throughout:

- API units expose only contract files under `services/api/app/contracts/`
- Discord units expose only contract files under `services/discord/app/contracts/` plus the API contract files they consume
- Test agents do not see `services/*/services/`, `repositories/`, `infrastructure/`, or endpoint implementations

## Work Unit Inventory

Total work units: `78`

| Initiative | Work units |
|---|---|
| Phase 0: Foundations | WU-001, WU-002, WU-003, WU-003B, WU-004, WU-005, WU-006A, WU-006B, WU-007A, WU-007B, WU-007C, WU-008A, WU-008B, WU-009A, WU-009B, WU-009C, WU-009D, WU-010A, WU-010B, WU-010C, WU-010D, WU-010E |
| VS-001: Member onboarding with initial trust assessment | WU-011 to WU-013 |
| VS-002: Scoped authority with enforcement | WU-014, WU-015A, WU-015B |
| VS-003: Audit trail with causal correlation | WU-016A to WU-016B |
| VS-004: Policy versioning with configuration safety | WU-017 |
| VS-005: Chapter provisioning from templates | WU-018 to WU-020 |
| VS-006: Structured application intake with reviewer ownership | WU-021, WU-022, WU-023a, WU-023b |
| VS-007: Ticket creation and case lifecycle | WU-024, WU-025A-create, WU-025A-events, WU-025B, WU-025C, WU-026 |
| VS-008: Permission intent and drift detection | WU-027, WU-028A, WU-028B-api, WU-028B-discord |
| VS-009: Configurable operator notifications | WU-029A, WU-029B-materialize, WU-029B-deliver, WU-029C |
| VS-010: Advanced trust management | WU-030A to WU-030B |
| VS-015: Cross-subsystem operational views | WU-031 to WU-032 |
| VS-011: Roster management with role lifecycle | WU-033 to WU-034 |
| VS-012: Application interview and waitlist handling | WU-035, WU-036a, WU-036b |
| VS-013: SLA enforcement for tickets | WU-037 |
| VS-014: Temporary permission management | WU-038A to WU-038B |
| VS-016: Compliance rule evaluation with evidence | WU-039, WU-040A, WU-040B-extract, WU-040B-correct, WU-041A, WU-041B |
| VS-017: Chapter governance lifecycle | WU-042, WU-043A, WU-043B |
| VS-018: Leadership succession with context transfer | WU-044A, WU-044B, WU-045A-applications, WU-045A-tickets, WU-045B |

## Phase 0: Foundations

**Phase-boundary gate:** Phase 0 does not close until `DECISIONS.md` records the hosting decision and rationale aligned to the `infra/` baseline.

### WU-001: Persistence Substrate With Migrations

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
PersistenceSubstrateRead(database_url_env_var, alembic_ini_path, current_revision)
MigrationRevisionRead(revision, applied_at)
GET /api/v1/system/migrations/current -> MigrationRevisionRead
```
**Test boundary:** `services/api/app/contracts/persistence.py`
**Code boundary:** `migrations/env.py`, `migrations/script.py.mako`, `migrations/versions/wu-001_persistence.py`, `services/api/app/contracts/persistence.py`, `services/api/app/repositories/db.py`, `services/api/app/api/v1/endpoints/system.py`, `services/api/tests/test_persistence.py`
**Acceptance criteria:**
- [ ] A clean database upgrades to the current Alembic head with no manual steps.
- [ ] `GET /api/v1/system/migrations/current` returns the live applied revision.
- [ ] Failed writes roll back cleanly and leave no partial rows committed.
**Pipeline phase:** Deep
**Dependencies:** none
**Parallelizable with:** WU-009A, WU-009B

### WU-002: Mutation Primitive And Versioned Base Contracts

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
VersionedRead(version)
MutationRequest(expected_version, actor_id, reason?)
MutationResult(version, etag)
```
**Test boundary:** `services/api/app/contracts/base.py`, `services/api/app/contracts/mutations.py`
**Code boundary:** `services/api/app/contracts/base.py`, `services/api/app/contracts/mutations.py`, `services/api/app/services/mutations.py`, `services/api/app/repositories/mutations.py`, `services/api/tests/test_mutations.py`
**Acceptance criteria:**
- [ ] Versioned read contracts serialize `version` and emit an ETag derived from the same value.
- [ ] A mutation with `expected_version == current_version` succeeds and increments the version by exactly 1.
- [ ] A mutation with stale `expected_version` returns `412 Precondition Failed`.
**Pipeline phase:** Standard
**Dependencies:** WU-001 (durable session and transaction substrate)
**Parallelizable with:** WU-010A, WU-010B

### WU-003: Audit Registry And Correlation Context Foundation

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
CorrelationHeadersRead(x_correlation_id, x_causation_id?)
AuditContextRead(correlation_id, causation_id?, headers: CorrelationHeadersRead)
AuditEntryRead(id, timestamp, actor_id, action_type, target_type, target_id, correlation: AuditContextRead, context)
```
**Test boundary:** `services/api/app/contracts/audit.py`
**Code boundary:** `migrations/versions/wu-003_audit_foundation.py`, `services/api/app/contracts/audit.py`, `services/api/app/core/context.py`, `services/api/app/repositories/audit.py`, `services/api/app/services/audit.py`, `services/api/tests/test_audit_foundation.py`
**Acceptance criteria:**
- [ ] Audit entries are append-only and immutable after insert.
- [ ] An incoming `X-Correlation-Id` is preserved; a missing one generates a new UUID.
- [ ] Root events persist `causation_id = null`; downstream events persist the same `correlation_id` and direct parent `causation_id`.
**Pipeline phase:** Deep
**Dependencies:** WU-001 (durable storage), WU-002 (shared mutation versioning)
**Parallelizable with:** WU-010C

### WU-003B: Notification Event Envelope Foundation

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
NotificationEventRead(id, event_type, correlation_id, causation_id?, scope_kind, scope_id?, payload, created_at)
```
**Test boundary:** `services/api/app/contracts/notifications.py`
**Code boundary:** `services/api/app/contracts/notifications.py`, `services/api/app/repositories/notification_events.py`, `services/api/app/services/notification_events.py`, `services/api/tests/test_notification_event_contract.py`
**Acceptance criteria:**
- [ ] Notification events preserve the originating `correlation_id` and optional direct `causation_id`.
- [ ] Notification events serialize to a documented JSON envelope that downstream workers can replay or export.
- [ ] Persisted notification events can be replayed after process restart and still materialize the same downstream event payload.
**Pipeline phase:** Standard
**Dependencies:** WU-003 (audit correlation foundation)
**Parallelizable with:** WU-004, WU-005, WU-006A, WU-007A, WU-007B, WU-008A, WU-009C, WU-009D, WU-010D, WU-010E

### WU-004: Authority Grant Foundation

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
AuthorityGrantRead(id, grantee_id, scope_kind, scope_id, permissions, expires_at?, revoked_at?, predecessor_grant_id?, version)
AuthorityRequirement(scope_kind, scope_id, permission)
```
**Test boundary:** `services/api/app/contracts/authority.py`
**Code boundary:** `migrations/versions/wu-004_authority_foundation.py`, `services/api/app/contracts/authority.py`, `services/api/app/repositories/authority.py`, `services/api/app/services/authority.py`, `services/api/tests/test_authority_foundation.py`
**Acceptance criteria:**
- [ ] Grants persist scope, permission set, expiry, and predecessor linkage.
- [ ] Authority evaluation returns allow only when scope and permission both match.
- [ ] Revoked or expired grants never satisfy an `AuthorityRequirement`.
- [ ] Authority grants round-trip to a documented JSON export shape without implementation-only fields.
**Pipeline phase:** Standard
**Dependencies:** WU-001 (persistence), WU-002 (mutation base), WU-003 (audit registry)
**Parallelizable with:** WU-003B, WU-005, WU-006A, WU-007A, WU-007B, WU-008A, WU-009C, WU-009D, WU-010D, WU-010E

### WU-005: Policy Version Preview-Confirm Foundation

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
PolicyPreviewRequest(policy_type, scope_kind, scope_id?, expected_current_version, content)
PolicyPreviewRead(preview_token, current_version, affected_objects, rollback_summary)
PolicyVersionRead(id, policy_type, version_number, effective_at)
```
**Test boundary:** `services/api/app/contracts/policies.py`
**Code boundary:** `migrations/versions/wu-005_policy_foundation.py`, `services/api/app/contracts/policies.py`, `services/api/app/repositories/policies.py`, `services/api/app/services/policies.py`, `services/api/tests/test_policy_foundation.py`
**Acceptance criteria:**
- [ ] Preview captures current version and proposed content without mutating active policy state.
- [ ] Confirming a preview persists a new policy version with `version_number = current + 1`.
- [ ] Confirming a stale preview returns `412 Precondition Failed`.
- [ ] Policy versions round-trip to a documented JSON export shape that preserves scope and version lineage.
**Pipeline phase:** Standard
**Dependencies:** WU-001 (persistence), WU-002 (mutation base), WU-003 (audit context)
**Parallelizable with:** WU-003B, WU-004, WU-006A, WU-007A, WU-007B, WU-008A, WU-009C, WU-009D, WU-010D, WU-010E

### WU-006A: Permission Intent Foundation

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
PermissionIntentRead(id, scope_kind, scope_id?, role_id, channel_id?, permission_bits, reason, temporary, expires_at?, version)
```
**Test boundary:** `services/api/app/contracts/permissions.py`, `services/api/app/contracts/base.py`
**Code boundary:** `migrations/versions/wu-006a_permission_intents_foundation.py`, `services/api/app/contracts/permissions.py`, `services/api/app/repositories/permissions.py`, `services/api/app/services/permissions.py`, `services/api/tests/test_permission_intent_foundation.py`
**Acceptance criteria:**
- [ ] Permission intent contracts support both server-level and channel-level shapes.
- [ ] Temporary intents require `expires_at`.
- [ ] Non-temporary intents reject `expires_at`-only updates.
- [ ] Permission intents round-trip to a documented JSON export shape that can be consumed outside the runtime.
**Pipeline phase:** Standard
**Dependencies:** WU-001 (persistence), WU-002 (version base), WU-003 (audit registry)
**Parallelizable with:** WU-003B, WU-004, WU-005, WU-007A, WU-007B, WU-008A, WU-009C, WU-009D, WU-010D, WU-010E

### WU-006B: Permission Drift Foundation

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
PermissionDriftRead(id, permission_intent_id?, actual_bits, intended_bits?, status in ["detected", "acknowledged", "reconciled", "accepted"], version)
```
**Test boundary:** `services/api/app/contracts/permissions.py`, `services/api/app/contracts/base.py`
**Code boundary:** `migrations/versions/wu-006b_permission_drift_foundation.py`, `services/api/app/contracts/permissions.py`, `services/api/app/repositories/permissions.py`, `services/api/app/services/permissions.py`, `services/api/tests/test_permission_drift_foundation.py`
**Acceptance criteria:**
- [ ] Drift contracts represent intended-versus-actual mismatch and unknown external state.
- [ ] A drift row may reference a permission intent or stand alone when no intent exists.
- [ ] Drift rows are versioned for later resolution workflows.
- [ ] Drift rows round-trip to a documented JSON export shape that preserves orphaned-versus-intent-linked state.
**Pipeline phase:** Standard
**Dependencies:** WU-001 (persistence), WU-002 (version base), WU-003 (audit registry), WU-006A (intent foreign-key substrate)
**Parallelizable with:** WU-007C, WU-008B

### WU-007A: Chapter Template Foundation

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
ChapterTemplateRead(id, name, channel_structure, role_structure, default_permission_intents, version)
```
**Test boundary:** `services/api/app/contracts/chapter_templates.py`, `services/api/app/contracts/base.py`
**Code boundary:** `migrations/versions/wu-007a_chapter_templates_foundation.py`, `services/api/app/contracts/chapter_templates.py`, `services/api/app/repositories/chapter_templates.py`, `services/api/app/services/chapter_templates.py`, `services/api/tests/test_chapter_template_foundation.py`
**Acceptance criteria:**
- [ ] Template contracts encode channel structure, role structure, and default permission intents separately.
- [ ] Templates are versioned for later safe updates.
- [ ] Template reads round-trip nested structure losslessly.
- [ ] Templates round-trip to a documented JSON export shape suitable for portability and re-import.
**Pipeline phase:** Standard
**Dependencies:** WU-001 (persistence), WU-002 (version base), WU-003 (audit registry)
**Parallelizable with:** WU-003B, WU-004, WU-005, WU-006A, WU-007B, WU-008A, WU-009C, WU-009D, WU-010D, WU-010E

### WU-007B: Chapter Role Foundation

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
ChapterRoleRead(id, chapter_id, name, ordinal, triggers_succession, version)
```
**Test boundary:** `services/api/app/contracts/chapter_roles.py`, `services/api/app/contracts/base.py`
**Code boundary:** `migrations/versions/wu-007b_chapter_roles_foundation.py`, `services/api/app/contracts/chapter_roles.py`, `services/api/app/repositories/chapter_roles.py`, `services/api/app/services/chapter_roles.py`, `services/api/tests/test_chapter_role_foundation.py`
**Acceptance criteria:**
- [ ] Chapter role contracts preserve ordinal ordering and succession flags.
- [ ] Roles are versioned independently of chapter templates.
- [ ] Role reads preserve stable identity for later roster references.
- [ ] Chapter roles round-trip to a documented JSON export shape that preserves ordering and succession metadata.
**Pipeline phase:** Standard
**Dependencies:** WU-001 (persistence), WU-002 (version base), WU-003 (audit registry)
**Parallelizable with:** WU-003B, WU-004, WU-005, WU-006A, WU-007A, WU-008A, WU-009C, WU-009D, WU-010D, WU-010E

### WU-007C: Roster Foundation

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
RosterEntryRead(id, chapter_id, member_id, role_id, status in ["active", "on_leave", "under_review", "removed"], version)
```
**Test boundary:** `services/api/app/contracts/roster.py`, `services/api/app/contracts/base.py`
**Code boundary:** `migrations/versions/wu-007c_roster_foundation.py`, `services/api/app/contracts/roster.py`, `services/api/app/repositories/roster.py`, `services/api/app/services/roster.py`, `services/api/tests/test_roster_foundation.py`
**Acceptance criteria:**
- [ ] Roster entry contracts carry optimistic-locking version state.
- [ ] Every roster row references a chapter role ID.
- [ ] Status values are constrained to the declared roster lifecycle set.
- [ ] Roster entries round-trip to a documented JSON export shape that preserves chapter, member, role, and lifecycle identity.
**Pipeline phase:** Standard
**Dependencies:** WU-001 (persistence), WU-002 (version base), WU-003 (audit registry), WU-007B (chapter role identity)
**Parallelizable with:** WU-006B, WU-008B

### WU-008A: Scheduler Foundation

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
ScheduledJobRead(job_key, handler_name, next_run_at)
```
**Test boundary:** `services/api/app/contracts/scheduler.py`
**Code boundary:** `migrations/versions/wu-008a_scheduler_foundation.py`, `services/api/app/contracts/scheduler.py`, `services/api/app/repositories/scheduler.py`, `services/api/app/services/scheduler.py`, `services/api/tests/test_scheduler_foundation.py`
**Acceptance criteria:**
- [ ] Scheduled jobs persist a stable `job_key` and survive service restart.
- [ ] Job identity is independent from next-run state.
- [ ] Scheduler registration is idempotent across repeated boots.
**Pipeline phase:** Deep
**Dependencies:** WU-001 (persistence), WU-003 (audit context)
**Parallelizable with:** WU-003B, WU-004, WU-005, WU-006A, WU-007A, WU-007B, WU-009C, WU-009D, WU-010D, WU-010E

### WU-008B: Deferred-Effect Foundation

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
DeferredEffectRead(id, effect_type, consequence_level in ["low", "consequential"], precondition_status in ["valid", "invalid", "unchecked"], queued_at)
DegradedStateSummaryRead(subsystem, pending_effect_count)
```
**Test boundary:** `services/api/app/contracts/scheduler.py`
**Code boundary:** `migrations/versions/wu-008b_deferred_effect_foundation.py`, `services/api/app/contracts/scheduler.py`, `services/api/app/repositories/deferred_effects.py`, `services/api/app/services/deferred_effects.py`, `services/api/app/tasks/__init__.py`, `services/api/tests/test_deferred_effect_foundation.py`
**Acceptance criteria:**
- [ ] Consequential effects never execute without explicit precondition validation state.
- [ ] Deferred effects are queryable independently from scheduled jobs.
- [ ] The degraded-state summary reports queued effects by subsystem without blocking unrelated writes.
**Pipeline phase:** Deep
**Dependencies:** WU-001 (persistence), WU-003 (audit context), WU-008A (scheduler substrate)
**Parallelizable with:** WU-006B, WU-007C

### WU-009A: API Test Harness Foundation

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
ApiTestHarnessRead(app_fixture, async_client_fixture, db_session_fixture, actor_context_fixture)
```
**Test boundary:** `services/api/app/contracts/testing.py`
**Code boundary:** `services/api/app/contracts/testing.py`, `services/api/tests/conftest.py`, `services/api/tests/test_harness.py`
**Acceptance criteria:**
- [ ] API tests run from the monorepo root with database and actor-context fixtures available.
- [ ] The API harness exposes only fixture contracts and does not leak service or repository internals into test boundaries.
- [ ] Harness contracts are imported from contract modules instead of service or infrastructure implementations.
**Pipeline phase:** Standard
**Dependencies:** none
**Parallelizable with:** WU-001, WU-009B

### WU-009B: Discord Test Harness Foundation

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
DiscordTestHarnessRead(bot_fixture, api_client_stub_fixture, interaction_factory_fixture)
```
**Test boundary:** `services/discord/app/contracts/testing.py`
**Code boundary:** `services/discord/app/contracts/testing.py`, `services/discord/tests/conftest.py`, `services/discord/tests/test_harness.py`
**Acceptance criteria:**
- [ ] Discord tests run without network access and stub API calls through a single fixture boundary.
- [ ] Interaction fixtures expose command options, actor identity, and correlation metadata through contract modules only.
- [ ] The harness can boot the Discord command registry without live guild access.
**Pipeline phase:** Standard
**Dependencies:** none
**Parallelizable with:** WU-001, WU-009A

### WU-009C: Discord Interaction Registry And Dispatch Foundation

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
InteractionEnvelope(command_name, interaction_id, actor_discord_user_id, channel_id?, options, correlation_id)
InteractionHandler.handle(envelope: InteractionEnvelope) -> InteractionResponseAck
```
**Test boundary:** `services/discord/app/contracts/interactions.py`, `services/api/app/contracts/audit.py`
**Code boundary:** `services/discord/app/contracts/interactions.py`, `services/discord/app/core/bot.py`, `services/discord/app/commands/__init__.py`, `services/discord/app/handlers/__init__.py`, `services/discord/tests/test_interaction_framework.py`
**Acceptance criteria:**
- [ ] Bot startup registers commands from a single registry and routes interactions through handler dispatch.
- [ ] Handler dispatch receives a stable interaction envelope that already carries correlation context.
- [ ] Downstream Discord feature units add only command and handler logic and do not modify registry or dispatch plumbing outside this unit.
**Pipeline phase:** Deep
**Dependencies:** WU-003 (correlation context), WU-009B (Discord test harness), WU-010B (Discord settings contract)
**Parallelizable with:** WU-003B, WU-004, WU-005, WU-006A, WU-007A, WU-007B, WU-008A, WU-009D, WU-010D, WU-010E

### WU-009D: Discord API Transport Foundation

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
ApiTransportRequest(method, path, body?, correlation_id, causation_id?)
ApiTransportResponse(status_code, payload)
ApiTransportPort.request(request: ApiTransportRequest) -> ApiTransportResponse
```
**Test boundary:** `services/discord/app/contracts/api_transport.py`, `services/api/app/contracts/audit.py`
**Code boundary:** `services/discord/app/contracts/api_transport.py`, `services/discord/app/infrastructure/api_client.py`, `services/discord/tests/test_api_transport.py`
**Acceptance criteria:**
- [ ] Transport requests preserve `correlation_id` and optional `causation_id` on every API call.
- [ ] Transport returns a stable response wrapper that feature units map to typed API contracts locally.
- [ ] Typed member, chapter, application, ticket, and roster helper calls are introduced only in the consuming feature units, not in this foundation unit.
**Pipeline phase:** Standard
**Dependencies:** WU-003 (audit correlation foundation), WU-009B (Discord test harness), WU-010B (Discord settings contract)
**Parallelizable with:** WU-003B, WU-004, WU-005, WU-006A, WU-007A, WU-007B, WU-008A, WU-009C, WU-010D, WU-010E

### WU-010A: API Service Settings Substrate

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
ApiSettings(database_url, supabase_service_key, app_version)
SettingsSourceRead(required_env_vars, optional_env_vars, secret_mounts)
```
**Test boundary:** `services/api/app/contracts/runtime_settings.py`
**Code boundary:** `services/api/app/contracts/runtime_settings.py`, `services/api/app/core/settings.py`, `services/api/tests/test_settings.py`
**Acceptance criteria:**
- [ ] The API service fails fast when required secrets are missing.
- [ ] API settings load from the secret and environment variable names already referenced by checked-in `infra/` manifests.
- [ ] API settings contracts expose a documented source map so deploy-time configuration is inspectable without reading implementation code.
**Pipeline phase:** Deep
**Dependencies:** WU-009A (API test harness)
**Parallelizable with:** WU-002, WU-010B

### WU-010B: Discord Service Settings Substrate

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
DiscordSettings(discord_bot_token, discord_guild_id, api_base_url)
SettingsSourceRead(required_env_vars, optional_env_vars, secret_mounts)
```
**Test boundary:** `services/discord/app/contracts/runtime_settings.py`
**Code boundary:** `services/discord/app/contracts/runtime_settings.py`, `services/discord/app/core/settings.py`, `services/discord/tests/test_settings.py`
**Acceptance criteria:**
- [ ] The Discord service fails fast when required secrets are missing.
- [ ] Discord settings load from the secret and environment variable names already referenced by checked-in `infra/` manifests.
- [ ] Discord settings contracts expose a documented source map so deploy-time configuration is inspectable without reading implementation code.
**Pipeline phase:** Deep
**Dependencies:** WU-009B (Discord test harness)
**Parallelizable with:** WU-002, WU-010A

### WU-010C: API Factory And Liveness Substrate

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
ServiceHealthRead(status, service, version)
GET /api/v1/health -> ServiceHealthRead
create_api_app(settings: ApiSettings) -> FastAPI
```
**Test boundary:** `services/api/app/contracts/runtime.py`
**Code boundary:** `services/api/app/contracts/runtime.py`, `services/api/app/api/v1/endpoints/health.py`, `services/api/app/core/factory.py`, `infra/tests/test_api_runtime.py`
**Acceptance criteria:**
- [ ] `GET /api/v1/health` returns service identity and version without checking readiness dependencies.
- [ ] The API process boots against the checked-in `infra/` baseline without ad hoc manual wiring.
- [ ] Startup failures return a non-zero result and name the missing bootstrap dependency.
**Pipeline phase:** Deep
**Dependencies:** WU-009A (API test harness), WU-010A (API settings)
**Parallelizable with:** WU-003

### WU-010D: API Readiness Surface

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
ServiceReadinessDependencyRead(name, status, detail?)
ServiceReadinessRead(status, dependencies)
GET /api/v1/ready -> ServiceReadinessRead
```
**Test boundary:** `services/api/app/contracts/runtime.py`
**Code boundary:** `services/api/app/contracts/runtime.py`, `services/api/app/api/v1/endpoints/ready.py`, `infra/tests/test_api_readiness.py`
**Acceptance criteria:**
- [ ] `GET /api/v1/ready` reports database and daemon dependencies separately from liveness.
- [ ] Readiness responses name each blocking dependency instead of collapsing them into a single generic failure.
- [ ] Readiness checks reuse the API factory bootstrap and do not duplicate service startup wiring.
**Pipeline phase:** Standard
**Dependencies:** WU-001 (persistence substrate), WU-010C (API factory and liveness)
**Parallelizable with:** WU-003B, WU-004, WU-005, WU-006A, WU-007A, WU-007B, WU-008A, WU-009C, WU-009D, WU-010E

### WU-010E: Discord Runtime Entrypoint

**Parent initiative:** Phase 0: Foundations
**Contract:**
```text
DiscordRuntimeRead(status, guild_id, api_base_url)
run_discord_daemon(settings: DiscordSettings) -> DiscordRuntimeRead
```
**Test boundary:** `services/discord/app/contracts/runtime.py`
**Code boundary:** `services/discord/app/contracts/runtime.py`, `services/discord/app/__main__.py`, `infra/tests/test_discord_runtime.py`
**Acceptance criteria:**
- [ ] The Discord process boots against the checked-in `infra/` baseline without ad hoc manual wiring.
- [ ] Runtime startup failures return a non-zero result and name the missing dependency.
- [ ] Discord runtime wiring stays isolated from API liveness and readiness endpoints.
**Pipeline phase:** Deep
**Dependencies:** WU-009B (Discord test harness), WU-010B (Discord settings)
**Parallelizable with:** WU-003B, WU-004, WU-005, WU-006A, WU-007A, WU-007B, WU-008A, WU-009C, WU-009D, WU-010D

## Phase 1: Governance Foundation

### VS-001: Member Onboarding With Initial Trust Assessment

#### WU-011: Member Aggregate And Status API

**Parent initiative:** VS-001: Member onboarding with initial trust assessment
**Contract:**
```text
MemberCreate(discord_user_id)
MemberRead(id, discord_user_id, joined_at, status in ["active", "suspended", "departed"], version)
MemberStatusChange(expected_version, to_status, reason)
POST /api/v1/members -> MemberRead
GET /api/v1/members/{member_id} -> MemberRead
GET /api/v1/members/by-discord/{discord_user_id} -> MemberRead
PATCH /api/v1/members/{member_id}/status -> MemberRead
```
**Test boundary:** `services/api/app/contracts/base.py`, `services/api/app/contracts/members.py`
**Code boundary:** `migrations/versions/wu-011_members.py`, `services/api/app/contracts/members.py`, `services/api/app/repositories/members.py`, `services/api/app/services/members.py`, `services/api/app/api/v1/endpoints/members.py`, `services/api/tests/test_members.py`
**Acceptance criteria:**
- [ ] `POST /api/v1/members` returns `201` with `status == "active"` and a server-assigned `id`.
- [ ] `GET /api/v1/members/by-discord/{discord_user_id}` returns the current member record for onboarding lookup.
- [ ] Read with version `N`, update with `expected_version = N`, then retry with stale `N` returns `412 Precondition Failed`.
**Decomposition note:** Kept as one API unit because member creation and status mutation share the same versioned member aggregate boundary.
**Pipeline phase:** Standard
**Dependencies:** WU-001 (persistence), WU-002 (version base), WU-003 (audit registry), WU-009A (API harness)
**Parallelizable with:** WU-014

#### WU-012: Trust Profile And Initial Computation API

**Parent initiative:** VS-001: Member onboarding with initial trust assessment
**Contract:**
```text
TrustProfileRead(member_id, score, tier, signals, intake_required, version)
POST /api/v1/trust/compute/{member_id} -> TrustProfileRead
GET /api/v1/trust/{member_id} -> TrustProfileRead
```
**Test boundary:** `services/api/app/contracts/trust.py`, `services/api/app/contracts/members.py`, `services/api/app/contracts/policies.py`
**Code boundary:** `migrations/versions/wu-012_trust.py`, `services/api/app/contracts/trust.py`, `services/api/app/repositories/trust.py`, `services/api/app/services/trust.py`, `services/api/app/api/v1/endpoints/trust.py`, `services/api/tests/test_trust.py`
**Acceptance criteria:**
- [ ] Initial computation persists a trust profile for an existing member.
- [ ] Computation uses the current trust policy version.
- [ ] Re-computation with the same input is deterministic at the same policy version.
**Decomposition note:** Kept as one API unit because trust profile reads and initial computation are a single trust-profile capability with one contract surface.
**Pipeline phase:** Standard
**Dependencies:** WU-003 (audit correlation), WU-005 (policy version foundation), WU-011 (member aggregate)
**Parallelizable with:** WU-015A

#### WU-013: Discord Member-Join Onboarding Flow

**Parent initiative:** VS-001: Member onboarding with initial trust assessment
**Contract:**
```text
MemberJoinEvent(discord_user_id, joined_at)
MemberJoinOutcomeRead(member_id, trust_profile_id, intake_required)
handler handle_member_join(event: MemberJoinEvent) -> MemberJoinOutcomeRead
```
**Test boundary:** `services/discord/app/contracts/onboarding.py`, `services/api/app/contracts/members.py`, `services/api/app/contracts/trust.py`
**Code boundary:** `services/discord/app/contracts/onboarding.py`, `services/discord/app/handlers/onboarding.py`, `services/discord/tests/test_onboarding.py`
**Acceptance criteria:**
- [ ] A Discord join event creates or finds the member record through the member API.
- [ ] The handler requests initial trust computation through the trust API.
- [ ] The handler returns `intake_required` from API configuration rather than Discord-local logic.
**Pipeline phase:** Standard
**Dependencies:** WU-009C (Discord interaction registry and dispatch), WU-009D (Discord API transport), WU-010B (Discord settings and API base URL), WU-010E (Discord runtime entrypoint), WU-011 (member API), WU-012 (trust API)
**Parallelizable with:** WU-015B, WU-016A

### VS-002: Scoped Authority With Enforcement

#### WU-014: Authority Grant Lifecycle API

**Parent initiative:** VS-002: Scoped authority with enforcement
**Contract:**
```text
AuthorityGrantCreate(grantee_id, scope_kind, scope_id, permissions, expires_at?)
AuthorityGrantRevoke(reason)
POST /api/v1/authority-grants -> AuthorityGrantRead
GET /api/v1/authority-grants?grantee_id={uuid}&scope_kind={kind}&scope_id={id}
POST /api/v1/authority-grants/{grant_id}/revoke -> AuthorityGrantRead
```
**Test boundary:** `services/api/app/contracts/authority.py`
**Code boundary:** `migrations/versions/wu-014_authority_api.py`, `services/api/app/contracts/authority.py`, `services/api/app/repositories/authority.py`, `services/api/app/services/authority.py`, `services/api/app/api/v1/endpoints/authority.py`, `services/api/tests/test_authority.py`
**Acceptance criteria:**
- [ ] `POST /api/v1/authority-grants` returns a persisted grant with the requested scope and permissions.
- [ ] Revoking a grant sets `revoked_at`, `revoked_by`, and `revocation_reason`.
- [ ] Filtering by grantee and scope returns only active grants matching the supplied scope.
**Pipeline phase:** Standard
**Dependencies:** WU-004 (authority foundation), WU-003 (audit foundation), WU-009A (API harness)
**Parallelizable with:** WU-011

#### WU-015A: Authority Enforcement Guard

**Parent initiative:** VS-002: Scoped authority with enforcement
**Contract:**
```text
AuthorityDecisionRead(allowed, grant_id?, denial_reason?, override_used)
```
**Test boundary:** `services/api/app/contracts/authority.py`, `services/api/app/contracts/audit.py`
**Code boundary:** `services/api/app/contracts/authority.py`, `services/api/app/core/dependencies.py`, `services/api/app/services/authority.py`, `services/api/tests/test_authority_enforcement.py`
**Acceptance criteria:**
- [ ] A write surface guarded by chapter scope returns `403` when the actor has no matching grant.
- [ ] The same surface succeeds when the actor holds a grant covering the scope and permission.
- [ ] Guard decisions return `override_used == false` unless an explicit override request is supplied by a downstream surface.
**Pipeline phase:** Standard
**Dependencies:** WU-014 (grant lifecycle API)
**Parallelizable with:** WU-012

#### WU-015B: Override Audit Policy

**Parent initiative:** VS-002: Scoped authority with enforcement
**Contract:**
```text
OverrideRequest(reason)
AuthorityDecisionRead(allowed, grant_id?, denial_reason?, override_used)
```
**Test boundary:** `services/api/app/contracts/authority.py`, `services/api/app/contracts/audit.py`
**Code boundary:** `services/api/app/contracts/authority.py`, `services/api/app/services/authority.py`, `services/api/app/services/audit_overrides.py`, `services/api/tests/test_authority_override_audit.py`
**Acceptance criteria:**
- [ ] A global override requires a non-empty reason.
- [ ] Every successful override records an `override_used` audit entry under the active correlation ID.
- [ ] Override audit policy reuses the guard decision surface and does not duplicate scope evaluation logic.
**Pipeline phase:** Standard
**Dependencies:** WU-003 (audit context), WU-015A (authority enforcement guard)
**Parallelizable with:** WU-013, WU-016A

### VS-003: Audit Trail With Causal Correlation

#### WU-016A: Audit Query API

**Parent initiative:** VS-003: Audit trail with causal correlation
**Contract:**
```text
GET /api/v1/audit/{entry_id} -> AuditEntryRead
GET /api/v1/audit?correlation_id={uuid} -> list[AuditEntryRead]
GET /api/v1/audit/{entry_id}/chain -> list[AuditEntryRead]
```
**Test boundary:** `services/api/app/contracts/audit.py`
**Code boundary:** `services/api/app/api/v1/endpoints/audit.py`, `services/api/app/repositories/audit.py`, `services/api/app/services/audit_queries.py`, `services/api/tests/test_audit_api.py`
**Acceptance criteria:**
- [ ] `GET /api/v1/audit?correlation_id={uuid}` returns the full causal chain ordered by timestamp.
- [ ] `GET /api/v1/audit/{entry_id}/chain` traces backward to the root event using `causation_id`.
- [ ] Scoped audit queries reuse the authority guard rather than duplicating permission checks.
**Pipeline phase:** Standard
**Dependencies:** WU-003 (audit foundation), WU-015A (authority guard for scoped queries)
**Parallelizable with:** WU-013, WU-015B

#### WU-016B: Discord Correlation Propagation Adapter

**Parent initiative:** VS-003: Audit trail with causal correlation
**Contract:**
```text
ApiRequestContext(correlation_id, causation_id?)
ApiRequestHeaders(x_correlation_id, x_causation_id?)
ApiContextPort.attach(context: ApiRequestContext) -> ApiRequestHeaders
```
**Test boundary:** `services/discord/app/contracts/api_transport.py`, `services/api/app/contracts/audit.py`
**Code boundary:** `services/discord/app/contracts/api_transport.py`, `services/discord/app/core/request_context.py`, `services/discord/tests/test_api_context.py`
**Acceptance criteria:**
- [ ] Discord-originated API calls preserve the correlation context they received from the originating interaction or scheduled task.
- [ ] Missing causation IDs remain null instead of being synthesized locally.
- [ ] The adapter does not expose Discord-only request shapes to API contracts.
**Pipeline phase:** Standard
**Dependencies:** WU-009D (Discord API transport), WU-010E (Discord runtime entrypoint), WU-016A (stable audit query and context contract)
**Parallelizable with:** WU-017

### VS-004: Policy Versioning With Configuration Safety

#### WU-017: Generic Policy Preview-Confirm API

**Parent initiative:** VS-004: Policy versioning with configuration safety
**Contract:**
```text
POST /api/v1/policies/preview -> PolicyPreviewRead
PolicyConfirmRequest(preview_token, expected_current_version)
POST /api/v1/policies/confirm -> PolicyVersionRead
GET /api/v1/policies/{policy_type}/current?scope_kind={kind}&scope_id={id} -> PolicyVersionRead
```
**Test boundary:** `services/api/app/contracts/policies.py`, `services/api/app/contracts/base.py`
**Code boundary:** `services/api/app/contracts/policies.py`, `services/api/app/api/v1/endpoints/policies.py`, `services/api/app/repositories/policies.py`, `services/api/app/services/policies.py`, `services/api/tests/test_policies.py`
**Acceptance criteria:**
- [ ] Preview returns `current_version`, a deterministic diff summary, and a stable `preview_token`.
- [ ] Confirm persists exactly one new policy version when `expected_current_version` matches the live version.
- [ ] Confirm against a superseded preview returns `412 Precondition Failed` and leaves active policy unchanged.
**Pipeline phase:** Standard
**Dependencies:** WU-005 (policy foundation), WU-015A (authority enforcement guard), WU-016A (audit query and correlation substrate)
**Parallelizable with:** WU-016B

## Phase 2: Core Operational Workflows

### VS-005: Chapter Provisioning From Templates

#### WU-018: Chapter Template Management API

**Parent initiative:** VS-005: Chapter provisioning from templates
**Contract:**
```text
ChapterTemplateCreate(name, channel_structure, role_structure, default_permission_intents)
PATCH /api/v1/chapter-templates/{template_id} -> ChapterTemplateRead
GET /api/v1/chapter-templates/{template_id} -> ChapterTemplateRead
POST /api/v1/chapter-templates -> ChapterTemplateRead
```
**Test boundary:** `services/api/app/contracts/chapter_templates.py`, `services/api/app/contracts/base.py`
**Code boundary:** `migrations/versions/wu-018_chapter_templates.py`, `services/api/app/contracts/chapter_templates.py`, `services/api/app/repositories/chapter_templates.py`, `services/api/app/services/chapter_templates.py`, `services/api/app/api/v1/endpoints/chapters/templates.py`, `services/api/tests/test_chapter_templates.py`
**Acceptance criteria:**
- [ ] Template create returns `201` with stored channel and role structure.
- [ ] Template update with current version succeeds and increments template version by exactly 1.
- [ ] Template update with stale version returns `412 Precondition Failed`.
**Pipeline phase:** Standard
**Dependencies:** WU-007A (template foundation), WU-017 (runtime dependency: preview-confirm operating model for template updates; does not consume policy contract types)
**Parallelizable with:** WU-021, WU-024, WU-027, WU-029A, WU-030A, WU-031

#### WU-019: Chapter Lifecycle API

**Parent initiative:** VS-005: Chapter provisioning from templates
**Contract:**
```text
ChapterCreate(name, template_id, configuration)
ChapterTransitionRequest(expected_version, to_state in ["provisioning", "active"], reason, discord_resources?)
POST /api/v1/chapters -> ChapterRead
POST /api/v1/chapters/{chapter_id}/transitions -> ChapterRead
GET /api/v1/chapters/{chapter_id} -> ChapterRead
```
**Test boundary:** `services/api/app/contracts/chapters.py`, `services/api/app/contracts/base.py`
**Code boundary:** `migrations/versions/wu-019_chapter_lifecycle.py`, `services/api/app/contracts/chapters.py`, `services/api/app/repositories/chapters.py`, `services/api/app/services/chapters.py`, `services/api/app/api/v1/endpoints/chapters/lifecycle.py`, `services/api/tests/test_chapter_lifecycle.py`
**Acceptance criteria:**
- [ ] Creating a chapter returns `state == "proposed"` and the selected `template_id`.
- [ ] Transition `proposed -> provisioning` requires current version and records a reason.
- [ ] Transition `provisioning -> active` persists verified Discord resource IDs and rejects stale version with `412 Precondition Failed`.
**Pipeline phase:** Standard
**Dependencies:** WU-018 (template management), WU-015A (authority enforcement guard), WU-016A (audit chain)
**Parallelizable with:** WU-022, WU-025A-create, WU-028A, WU-029B-materialize, WU-030B

#### WU-020: Discord Chapter Provisioning Workflow

**Parent initiative:** VS-005: Chapter provisioning from templates
**Contract:**
```text
ChapterProvisionCommand(chapter_id)
ChapterProvisionResult(chapter_id, category_id, role_ids, channel_ids)
handler provision_chapter(command) -> ChapterProvisionResult
```
**Test boundary:** `services/discord/app/contracts/chapters.py`, `services/api/app/contracts/chapters.py`
**Code boundary:** `services/discord/app/contracts/chapters.py`, `services/discord/app/commands/chapters.py`, `services/discord/app/handlers/chapters.py`, `services/discord/tests/test_chapter_provisioning.py`
**Acceptance criteria:**
- [ ] The provisioning handler creates the Discord category, channels, and roles described by the selected template.
- [ ] After successful Discord creation, the handler confirms the provisioning result through the chapter lifecycle API.
- [ ] A failed downstream Discord step queues a consequential deferred effect instead of partially marking the chapter active.
**Pipeline phase:** Deep
**Dependencies:** WU-008B (deferred effects), WU-009C (Discord interaction registry and dispatch), WU-009D (Discord API transport), WU-010B (Discord settings), WU-010E (Discord runtime entrypoint), WU-019 (chapter lifecycle API)
**Parallelizable with:** WU-023a, WU-023b, WU-025A-events, WU-025B, WU-028B-discord, WU-029B-deliver, WU-032

### VS-006: Structured Application Intake With Reviewer Ownership

#### WU-021: Form Definition Version API

**Parent initiative:** VS-006: Structured application intake with reviewer ownership
**Contract:**
```text
FormDefinitionCreate(scope_kind, scope_id, schema, active_from)
FormDefinitionRead(id, scope_kind, scope_id, version_number, schema, active_from)
POST /api/v1/application-forms -> FormDefinitionRead
GET /api/v1/application-forms/current?scope_kind={kind}&scope_id={id} -> FormDefinitionRead
```
**Test boundary:** `services/api/app/contracts/applications.py`, `services/api/app/contracts/base.py`
**Code boundary:** `migrations/versions/wu-021_forms.py`, `services/api/app/contracts/applications.py`, `services/api/app/repositories/forms.py`, `services/api/app/services/forms.py`, `services/api/app/api/v1/endpoints/applications/forms.py`, `services/api/tests/test_forms.py`
**Acceptance criteria:**
- [ ] Publishing a form definition creates version `1` for a new scope.
- [ ] Publishing a replacement form increments the scope-local version number.
- [ ] Reading the current form returns the latest effective version for the requested scope.
**Pipeline phase:** Standard
**Dependencies:** WU-017 (runtime dependency: preview-confirm operating model for form updates; does not consume policy contract types), WU-015A (authority enforcement guard)
**Parallelizable with:** WU-018, WU-024, WU-027, WU-029A, WU-030A, WU-031

#### WU-022: Application Submission And Reviewer Ownership API

**Parent initiative:** VS-006: Structured application intake with reviewer ownership
**Contract:**
```text
ApplicationCreate(applicant_id, form_definition_id, target_scope_kind in ["chapter", "role"], target_scope_id, responses)
ApplicationRead(id, applicant_id, form_definition_id, form_version, state in ["submitted", "queued", "claimed", "in_review", "interview", "waitlisted", "approved", "denied", "withdrawn"], reviewer_id?, version)
ApplicationTransitionRequest(expected_version, action in ["claim", "start_review", "approve", "deny", "withdraw", "release_claim"], reason?)
POST /api/v1/applications -> ApplicationRead
POST /api/v1/applications/{application_id}/transitions -> ApplicationRead
```
**Test boundary:** `services/api/app/contracts/applications.py`, `services/api/app/contracts/members.py`, `services/api/app/contracts/trust.py`, `services/api/app/contracts/base.py`
**Code boundary:** `migrations/versions/wu-022_applications.py`, `services/api/app/contracts/applications.py`, `services/api/app/repositories/applications.py`, `services/api/app/services/applications.py`, `services/api/app/api/v1/endpoints/applications/lifecycle.py`, `services/api/tests/test_applications.py`
**Acceptance criteria:**
- [ ] `POST /api/v1/applications` creates `state == "submitted"` and automatically routes to `queued`.
- [ ] Claiming a queued application assigns exactly one reviewer; a second concurrent claim returns `409 Conflict`.
- [ ] Approve or deny with current version succeeds; a repeat transition with stale version returns `412 Precondition Failed`.
**Decomposition note:** Kept as one API unit because submission creation and reviewer-ownership transitions mutate the same application aggregate and versioned lifecycle contract.
**Pipeline phase:** Standard
**Dependencies:** WU-011 (member aggregate), WU-012 (trust profile API), WU-015A (authority enforcement guard), WU-016A (audit chain), WU-021 (form definition API)
**Parallelizable with:** WU-019, WU-025A-create, WU-028A, WU-029B-materialize, WU-030B

#### WU-023a: Discord Application Submission Flow

**Parent initiative:** VS-006: Structured application intake with reviewer ownership
**Contract:**
```text
ApplicationSubmissionCommand(form_id, applicant_discord_user_id, responses)
ApplicationSubmissionResult(application_id, correlation_id)
handler submit_application(command: ApplicationSubmissionCommand) -> ApplicationSubmissionResult
```
**Test boundary:** `services/discord/app/contracts/application_submission.py`, `services/api/app/contracts/applications.py`
**Code boundary:** `services/discord/app/contracts/application_submission.py`, `services/discord/app/commands/application_submission.py`, `services/discord/app/handlers/application_submission.py`, `services/discord/tests/test_application_submission.py`
**Acceptance criteria:**
- [ ] Submitting an application command sends the full response payload to the application API and returns the created application ID.
- [ ] Contract-defined validation or authorization failures surface back to the applicant flow without creating Discord-local reviewer state.
- [ ] Successful submission preserves the API correlation ID on the Discord-side result used by downstream notifications.
**Pipeline phase:** Standard
**Dependencies:** WU-009C (Discord interaction registry and dispatch), WU-009D (Discord API transport), WU-010B (Discord settings), WU-010E (Discord runtime entrypoint), WU-022 (application lifecycle API)
**Parallelizable with:** WU-020, WU-023b, WU-025A-events, WU-025B, WU-028B-discord, WU-029B-deliver, WU-032

#### WU-023b: Discord Application Review Flow

**Parent initiative:** VS-006: Structured application intake with reviewer ownership
**Contract:**
```text
ApplicationReviewCommand(application_id, action in ["claim", "approve", "deny"], reason?)
ApplicationReviewResult(application_id, state, correlation_id)
handler review_application(command: ApplicationReviewCommand) -> ApplicationReviewResult
```
**Test boundary:** `services/discord/app/contracts/application_review.py`, `services/api/app/contracts/applications.py`
**Code boundary:** `services/discord/app/contracts/application_review.py`, `services/discord/app/commands/application_review.py`, `services/discord/app/handlers/application_review.py`, `services/discord/tests/test_application_review.py`
**Acceptance criteria:**
- [ ] Reviewer claim and decision commands forward the published API transition contract without mutating Discord-local state before API success.
- [ ] Reviewer claim collisions surface API `409 Conflict` without posting duplicate review outcomes.
- [ ] Successful decisions post exactly one outcome summary tied to the same correlation ID as the API transition.
**Pipeline phase:** Standard
**Dependencies:** WU-009C (Discord interaction registry and dispatch), WU-009D (Discord API transport), WU-010B (Discord settings), WU-010E (Discord runtime entrypoint), WU-022 (application lifecycle API)
**Parallelizable with:** WU-020, WU-023a, WU-025A-events, WU-025B, WU-028B-discord, WU-029B-deliver, WU-032

### VS-007: Ticket Creation And Case Lifecycle

#### WU-024: Ticket Category Configuration API

**Parent initiative:** VS-007: Ticket creation and case lifecycle
**Contract:**
```text
TicketCategoryCreate(name, routing_scope, state_machine, privacy_level, sla_rules?)
TicketCategoryRead(id, name, routing_scope, state_machine, privacy_level, version)
POST /api/v1/ticket-categories -> TicketCategoryRead
PATCH /api/v1/ticket-categories/{category_id} -> TicketCategoryRead
```
**Test boundary:** `services/api/app/contracts/tickets.py`, `services/api/app/contracts/base.py`
**Code boundary:** `migrations/versions/wu-024_ticket_categories.py`, `services/api/app/contracts/tickets.py`, `services/api/app/repositories/ticket_categories.py`, `services/api/app/services/ticket_categories.py`, `services/api/app/api/v1/endpoints/tickets/categories.py`, `services/api/tests/test_ticket_categories.py`
**Acceptance criteria:**
- [ ] Category create persists routing scope, privacy level, and full state-machine definition.
- [ ] Category update with current version succeeds; stale version returns `412 Precondition Failed`.
- [ ] Categories without `sla_rules` remain valid and do not schedule SLA checks.
**Pipeline phase:** Standard
**Dependencies:** WU-017 (runtime dependency: preview-confirm operating model for ticket-category updates; does not consume policy contract types), WU-015A (authority enforcement guard)
**Parallelizable with:** WU-018, WU-021, WU-027, WU-029A, WU-030A, WU-031

#### WU-025A-create: Ticket Creation API

**Parent initiative:** VS-007: Ticket creation and case lifecycle
**Contract:**
```text
TicketCreate(category_id, reporter_id, subject_id?)
TicketRead(id, category_id, reporter_id, state, priority?, owner_id?, version)
POST /api/v1/tickets -> TicketRead
```
**Test boundary:** `services/api/app/contracts/tickets.py`, `services/api/app/contracts/base.py`
**Code boundary:** `migrations/versions/wu-025a_tickets_create.py`, `services/api/app/contracts/tickets.py`, `services/api/app/repositories/tickets.py`, `services/api/app/services/tickets.py`, `services/api/app/api/v1/endpoints/tickets/create.py`, `services/api/tests/test_ticket_create.py`
**Acceptance criteria:**
- [ ] Ticket create places the ticket in the category's configured initial state.
- [ ] Ticket create does not append or rewrite any ticket message events.
- [ ] Creating a ticket under an unknown or unauthorized category returns the contract-defined error response and creates no ticket row.
**Pipeline phase:** Standard
**Dependencies:** WU-015A (authority enforcement guard), WU-016A (audit chain), WU-024 (ticket-category config)
**Parallelizable with:** WU-019, WU-022, WU-028A, WU-029B-materialize, WU-030B

#### WU-025A-events: Ticket Initial Message Event Persistence

**Parent initiative:** VS-007: Ticket creation and case lifecycle
**Contract:**
```text
TicketMessageEventCreate(ticket_id, message, visibility in ["reporter", "staff"])
TicketMessageEventRead(message_id, ticket_id, visibility, created_at)
TicketMessageEventWriter.append_initial(event: TicketMessageEventCreate) -> TicketMessageEventRead
```
**Test boundary:** `services/api/app/contracts/ticket_messages.py`, `services/api/app/contracts/base.py`
**Code boundary:** `services/api/app/contracts/ticket_messages.py`, `services/api/app/repositories/ticket_messages.py`, `services/api/app/services/ticket_messages.py`, `services/api/tests/test_ticket_initial_message_events.py`
**Acceptance criteria:**
- [ ] Appending an initial message creates one immutable message event for an existing ticket.
- [ ] Initial message persistence rejects an unknown ticket ID and writes no event row.
- [ ] Initial message events preserve `visibility == "reporter"` on read and never rewrite prior message events.
**Pipeline phase:** Standard
**Dependencies:** WU-016A (audit chain), WU-025A-create (ticket aggregate identity)
**Parallelizable with:** WU-020, WU-023a, WU-023b, WU-025B, WU-028B-discord, WU-029B-deliver, WU-032

#### WU-025B: Ticket Transition API

**Parent initiative:** VS-007: Ticket creation and case lifecycle
**Contract:**
```text
TicketTransitionRequest(expected_version, action in ["triage", "assign", "escalate", "resolve", "close"], owner_id?, reason?, resolution?)
POST /api/v1/tickets/{ticket_id}/transitions -> TicketRead
```
**Test boundary:** `services/api/app/contracts/tickets.py`, `services/api/app/contracts/base.py`
**Code boundary:** `services/api/app/contracts/tickets.py`, `services/api/app/repositories/tickets.py`, `services/api/app/services/tickets.py`, `services/api/app/api/v1/endpoints/tickets/transitions.py`, `services/api/tests/test_ticket_transitions.py`
**Acceptance criteria:**
- [ ] Escalation requires a reason and follows only a transition allowed by the category state machine.
- [ ] Transitions that assign ownership persist the selected owner on the ticket aggregate.
- [ ] Read with version `N`, transition with `expected_version = N`, then retry with stale `N` returns `412 Precondition Failed`.
**Pipeline phase:** Standard
**Dependencies:** WU-015A (authority enforcement guard), WU-016A (audit chain), WU-024 (ticket-category config), WU-025A-create (ticket aggregate creation API)
**Parallelizable with:** WU-020, WU-023a, WU-023b, WU-025A-events, WU-028B-discord, WU-029B-deliver, WU-032

#### WU-025C: Ticket Message Append API

**Parent initiative:** VS-007: Ticket creation and case lifecycle
**Contract:**
```text
TicketMessageCreate(message, visibility in ["reporter", "staff", "internal_note"])
TicketMessageAppendRead(message_id, ticket_id, created_at)
POST /api/v1/tickets/{ticket_id}/messages -> TicketMessageAppendRead
```
**Test boundary:** `services/api/app/contracts/ticket_messages.py`, `services/api/app/contracts/base.py`
**Code boundary:** `services/api/app/contracts/ticket_messages.py`, `services/api/app/repositories/ticket_messages.py`, `services/api/app/services/ticket_messages.py`, `services/api/app/api/v1/endpoints/tickets/messages.py`, `services/api/tests/test_ticket_messages.py`
**Acceptance criteria:**
- [ ] `POST /api/v1/tickets/{ticket_id}/messages` appends a new immutable message event and never rewrites prior ticket messages.
- [ ] Appending a message does not mutate ticket state, ownership, or ticket version.
- [ ] Internal-note visibility never leaks into reporter-visible message reads.
**Pipeline phase:** Standard
**Dependencies:** WU-016A (audit chain), WU-025A-events (ticket message-event substrate), WU-025B (ticket transition API)
**Parallelizable with:** WU-026, WU-029C

#### WU-026: Discord Ticket Interaction Flow

**Parent initiative:** VS-007: Ticket creation and case lifecycle
**Contract:**
```text
TicketOpenCommand(category_id, reporter_discord_user_id, subject_discord_user_id?, initial_message)
TicketModerationCommand(ticket_id, action in ["triage", "assign", "escalate", "resolve", "close"], reason?)
```
**Test boundary:** `services/discord/app/contracts/tickets.py`, `services/api/app/contracts/tickets.py`
**Code boundary:** `services/discord/app/contracts/tickets.py`, `services/discord/app/commands/tickets.py`, `services/discord/app/handlers/tickets.py`, `services/discord/tests/test_tickets.py`
**Acceptance criteria:**
- [ ] Opening a ticket command creates the API ticket before the Discord thread or channel is created.
- [ ] Moderation commands forward transitions to the API and mutate Discord state only after API success.
- [ ] Discord-side transcript mapping preserves the API ticket ID for later message sync.
**Decomposition note:** Kept as one Discord unit because ticket opening and moderation share the same thread-bootstrap, transcript-correlation, and command-routing surface; splitting them would duplicate the same Discord handler seam across two PRs.
**Pipeline phase:** Standard
**Dependencies:** WU-009C (Discord interaction registry and dispatch), WU-009D (Discord API transport), WU-010B (Discord settings), WU-010E (Discord runtime entrypoint), WU-025A-create (ticket creation API), WU-025A-events (initial message-event persistence), WU-025B (ticket transition API)
**Parallelizable with:** WU-025C, WU-029C

### VS-008: Permission Intent And Drift Detection

#### WU-027: Permission Intent Management API

**Parent initiative:** VS-008: Permission intent and drift detection
**Contract:**
```text
PermissionIntentCreate(scope_kind, scope_id?, role_id, channel_id?, permission_bits, reason, temporary, expires_at?)
POST /api/v1/permission-intents -> PermissionIntentRead
PATCH /api/v1/permission-intents/{intent_id} -> PermissionIntentRead
GET /api/v1/permission-intents?scope_kind={kind}&scope_id={id} -> list[PermissionIntentRead]
```
**Test boundary:** `services/api/app/contracts/permissions.py`, `services/api/app/contracts/base.py`
**Code boundary:** `migrations/versions/wu-027_permission_intents.py`, `services/api/app/contracts/permissions.py`, `services/api/app/repositories/permissions.py`, `services/api/app/services/permissions.py`, `services/api/app/api/v1/endpoints/permissions/intents.py`, `services/api/tests/test_permission_intents.py`
**Acceptance criteria:**
- [ ] Creating an intent persists scope, target role, optional channel, and bitset exactly as provided.
- [ ] Updating an intent with current version succeeds; stale version returns `412 Precondition Failed`.
- [ ] Temporary intents preserve `expires_at` on read and reject creation without it.
**Pipeline phase:** Standard
**Dependencies:** WU-006A (permission intent foundation), WU-015A (authority enforcement guard), WU-016A (audit chain)
**Parallelizable with:** WU-018, WU-021, WU-024, WU-029A, WU-030A, WU-031

#### WU-028A: Permission Drift Read And Resolution API

**Parent initiative:** VS-008: Permission intent and drift detection
**Contract:**
```text
DriftResolutionRequest(expected_version, action in ["reconcile", "accept", "acknowledge"], reason?)
GET /api/v1/permission-drift -> list[PermissionDriftRead]
POST /api/v1/permission-drift/{drift_id}/resolve -> PermissionDriftRead
```
**Test boundary:** `services/api/app/contracts/permissions.py`, `services/api/app/contracts/base.py`
**Code boundary:** `migrations/versions/wu-028a_permission_drift_api.py`, `services/api/app/contracts/permissions.py`, `services/api/app/repositories/permissions.py`, `services/api/app/services/permissions.py`, `services/api/app/api/v1/endpoints/permissions/drift.py`, `services/api/tests/test_permission_drift.py`
**Acceptance criteria:**
- [ ] Drift reads return both intent-linked and orphaned drift rows.
- [ ] Resolving a drift with stale version returns `412 Precondition Failed`.
- [ ] `accept` and `acknowledge` transitions update only the drift row and leave intent state unchanged.
**Decomposition note:** Kept as one API unit because drift inspection and drift resolution are the read and mutation surface of the same drift resource.
**Pipeline phase:** Standard
**Dependencies:** WU-006B (permission drift foundation), WU-015A (authority enforcement guard), WU-016A (audit chain), WU-027 (permission-intent API)
**Parallelizable with:** WU-019, WU-022, WU-025A-create, WU-029B-materialize, WU-030B

#### WU-028B-api: Permission Reconciliation Run API

**Parent initiative:** VS-008: Permission intent and drift detection
**Contract:**
```text
PermissionReconciliationRunRequest(scope_kind?, scope_id?)
PermissionScopeSnapshotWrite(scope_kind, scope_id?, role_permissions, channel_permissions)
PermissionReconciliationRunRead(id, scope_kind?, scope_id?, status in ["received", "reconciled", "failed"], drift_ids)
POST /api/v1/permission-reconciliation/runs -> PermissionReconciliationRunRead
POST /api/v1/permission-reconciliation/runs/{run_id}/snapshots -> PermissionReconciliationRunRead
```
**Test boundary:** `services/api/app/contracts/permissions.py`, `services/api/app/contracts/base.py`
**Code boundary:** `services/api/app/contracts/permissions.py`, `services/api/app/repositories/permissions.py`, `services/api/app/services/permission_reconciliation.py`, `services/api/app/api/v1/endpoints/permissions/reconciliation.py`, `services/api/tests/test_permission_reconciliation_api.py`
**Acceptance criteria:**
- [ ] `POST /api/v1/permission-reconciliation/runs` persists a reconciliation run record for the requested scope.
- [ ] Submitting a typed snapshot creates a drift entry when Discord state differs from an existing intent.
- [ ] Submitting a typed snapshot creates a drift entry when Discord state exists with no matching intent.
- [ ] Snapshot submissions that omit typed role or channel permission collections are rejected by the contract-defined validation error.
**Pipeline phase:** Standard
**Dependencies:** WU-015A (authority enforcement guard), WU-016A (audit chain), WU-027 (permission-intent API), WU-028A (drift API)
**Parallelizable with:** none

#### WU-028B-discord: Discord Permission Snapshot Adapter

**Parent initiative:** VS-008: Permission intent and drift detection
**Contract:**
```text
ReconciliationRunCommand(run_id, scope_kind?, scope_id?)
PermissionScopeSnapshotRead(scope_kind, scope_id?, role_permissions, channel_permissions)
PermissionReconciliationSubmissionRead(run_id, status)
PermissionStatePort.fetch_scope_state(command: ReconciliationRunCommand) -> PermissionScopeSnapshotRead
handler submit_permission_snapshot(command: ReconciliationRunCommand) -> PermissionReconciliationSubmissionRead
```
**Test boundary:** `services/api/app/contracts/permissions.py`, `services/discord/app/contracts/permissions.py`
**Code boundary:** `services/discord/app/contracts/permissions.py`, `services/discord/app/infrastructure/permission_client.py`, `services/discord/app/handlers/permissions.py`, `services/discord/tests/test_permission_reconciliation_adapter.py`
**Acceptance criteria:**
- [ ] The adapter fetches actual Discord state for the requested scope and submits a typed snapshot to the API run created by `WU-028B-api`.
- [ ] Retrying the same reconciliation run reuses the API run ID as the idempotency key.
- [ ] The adapter never mutates drift rows locally and communicates with the API only through the published reconciliation contract.
**Pipeline phase:** Deep
**Dependencies:** WU-009D (Discord API transport), WU-010E (Discord runtime entrypoint), WU-028B-api (reconciliation run API)
**Parallelizable with:** WU-020, WU-023a, WU-023b, WU-025A-events, WU-025B, WU-029B-deliver, WU-032

### VS-009: Configurable Operator Notifications

#### WU-029A: Notification Rule Management API

**Parent initiative:** VS-009: Configurable operator notifications
**Contract:**
```text
NotificationRuleCreate(trigger, scope_kind, scope_id?, recipients, channel in ["dm", "thread", "designated_channel"], template, actionable, grouping in ["per_event", "per_root_cause"])
NotificationRuleRead(id, trigger, scope_kind, scope_id?, recipients, channel, template, actionable, grouping, version)
POST /api/v1/notification-rules -> NotificationRuleRead
GET /api/v1/notification-rules -> list[NotificationRuleRead]
```
**Test boundary:** `services/api/app/contracts/notifications.py`, `services/api/app/contracts/base.py`
**Code boundary:** `migrations/versions/wu-029a_notification_rules.py`, `services/api/app/contracts/notifications.py`, `services/api/app/repositories/notifications.py`, `services/api/app/services/notifications.py`, `services/api/app/api/v1/endpoints/notifications.py`, `services/api/tests/test_notification_rules.py`
**Acceptance criteria:**
- [ ] Creating a rule persists grouping, recipients, channel, and actionable flag exactly as submitted.
- [ ] Updating a rule with current version succeeds; stale version returns `412 Precondition Failed`.
- [ ] Listing rules returns only the rules visible to the caller's authorized scope.
**Pipeline phase:** Standard
**Dependencies:** WU-015A (authority enforcement guard), WU-016A (audit correlation substrate), WU-017 (runtime dependency: preview-confirm operating model for rule updates; does not consume policy contract types)
**Parallelizable with:** WU-018, WU-021, WU-024, WU-027, WU-030A, WU-031

#### WU-029B-materialize: Notification Envelope Materialization Worker

**Parent initiative:** VS-009: Configurable operator notifications
**Contract:**
```text
NotificationEnvelopeRead(id, correlation_id, recipient_ids, channel, actionable)
NotificationMaterializationResult(envelope_ids)
handler materialize_notification_envelopes(event: NotificationEventRead) -> NotificationMaterializationResult
```
**Test boundary:** `services/api/app/contracts/notifications.py`, `services/api/app/contracts/audit.py`
**Code boundary:** `services/api/app/contracts/notifications.py`, `services/api/app/tasks/notifications_materialize.py`, `services/api/app/services/notifications_materialize.py`, `services/api/tests/test_notification_materialization.py`
**Acceptance criteria:**
- [ ] A rule with `grouping == "per_root_cause"` emits one notification envelope per root correlation ID.
- [ ] A rule with `grouping == "per_event"` emits one notification envelope per triggering audit entry.
- [ ] Replaying the same persisted notification event does not materialize duplicate envelopes.
**Pipeline phase:** Standard
**Dependencies:** WU-003B (notification event envelope foundation), WU-016A (audit query/correlation), WU-029A (notification-rule API)
**Parallelizable with:** WU-019, WU-022, WU-025A-create, WU-028A, WU-030B

#### WU-029B-deliver: Scheduled Notification Delivery Worker

**Parent initiative:** VS-009: Configurable operator notifications
**Contract:**
```text
NotificationDeliveryBatchRead(delivered_envelope_ids, skipped_envelope_ids, failed_envelope_ids)
scheduled handler deliver_notifications() -> NotificationDeliveryBatchRead
```
**Test boundary:** `services/api/app/contracts/notifications.py`, `services/api/app/contracts/scheduler.py`
**Code boundary:** `services/api/app/contracts/notifications.py`, `services/api/app/tasks/notifications_deliver.py`, `services/api/app/services/notifications_delivery.py`, `services/api/tests/test_notification_delivery_worker.py`
**Acceptance criteria:**
- [ ] Scheduled delivery selects only materialized envelopes that are not yet marked delivered.
- [ ] Successful delivery marks each envelope exactly once.
- [ ] Re-running delivery skips already delivered envelopes and reports them in `skipped_envelope_ids`.
**Pipeline phase:** Standard
**Dependencies:** WU-008A (scheduler foundation), WU-029B-materialize (materialized envelope source)
**Parallelizable with:** WU-020, WU-023a, WU-023b, WU-025A-events, WU-025B, WU-028B-discord, WU-032

#### WU-029C: Discord Notification Delivery Adapter

**Parent initiative:** VS-009: Configurable operator notifications
**Contract:**
```text
NotificationDeliveryCommand(envelope: NotificationEnvelopeRead)
NotificationDeliveryResult(envelope_id, delivered_at)
handler deliver_notification(command: NotificationDeliveryCommand) -> NotificationDeliveryResult
```
**Test boundary:** `services/discord/app/contracts/notifications.py`, `services/api/app/contracts/notifications.py`
**Code boundary:** `services/discord/app/contracts/notifications.py`, `services/discord/app/handlers/notifications.py`, `services/discord/tests/test_notifications.py`
**Acceptance criteria:**
- [ ] Delivered notifications preserve `actionable` exactly as configured in the rule.
- [ ] Discord delivery uses the persisted envelope ID as the idempotency key.
- [ ] Delivery failures do not mutate the underlying rule definition.
**Pipeline phase:** Standard
**Dependencies:** WU-009C (Discord interaction registry and dispatch), WU-010E (Discord runtime entrypoint), WU-029B-deliver (delivery worker)
**Parallelizable with:** WU-025C, WU-026

### VS-010: Advanced Trust Management

#### WU-030A: Trust Signal Management API

**Parent initiative:** VS-010: Advanced trust management
**Contract:**
```text
TrustSignalCreate(member_id, signal_type, scope_kind, scope_id?, value, expires_at?)
POST /api/v1/trust/signals -> TrustSignalRead
```
**Test boundary:** `services/api/app/contracts/trust.py`, `services/api/app/contracts/policies.py`
**Code boundary:** `migrations/versions/wu-030_trust_signals.py`, `services/api/app/contracts/trust.py`, `services/api/app/repositories/trust.py`, `services/api/app/services/trust.py`, `services/api/app/api/v1/endpoints/trust/signals.py`, `services/api/tests/test_trust_signals.py`
**Acceptance criteria:**
- [ ] Creating a signal persists type, scope, value, and optional expiry.
- [ ] Signals preserve scope-specific values without mutating the current trust profile until recomputation is requested.
- [ ] Signal writes remain append-safe under the audit chain and do not bypass the policy version substrate.
**Pipeline phase:** Standard
**Dependencies:** WU-012 (trust profile API), WU-016A (audit chain), WU-017 (policy preview-confirm API)
**Parallelizable with:** WU-018, WU-021, WU-024, WU-027, WU-029A, WU-031

#### WU-030B: Trust Recomputation Trigger API

**Parent initiative:** VS-010: Advanced trust management
**Contract:**
```text
POST /api/v1/trust/recompute/{member_id} -> TrustProfileRead
```
**Test boundary:** `services/api/app/contracts/trust.py`, `services/api/app/contracts/policies.py`
**Code boundary:** `services/api/app/contracts/trust.py`, `services/api/app/services/trust.py`, `services/api/app/api/v1/endpoints/trust/recompute.py`, `services/api/tests/test_trust_recompute.py`
**Acceptance criteria:**
- [ ] Recompute pins the current trust policy version when producing the new profile.
- [ ] Recompute is deterministic for the same signal set and policy version.
- [ ] Recompute reads only persisted signal state and does not accept ad hoc Discord-local overrides.
**Pipeline phase:** Standard
**Dependencies:** WU-012 (trust profile API), WU-016A (audit chain), WU-017 (policy preview-confirm API), WU-030A (trust signal management API)
**Parallelizable with:** WU-019, WU-022, WU-025A-create, WU-028A, WU-029B-materialize

### VS-015: Cross-Subsystem Operational Views

#### WU-031: Audit Projection Read-Model Pipeline

**Parent initiative:** VS-015: Cross-subsystem operational views
**Contract:**
```text
ReadModelCursorRead(projector_name, last_audit_id, updated_at)
scheduled handler project_audit_read_models() -> ReadModelCursorRead
```
**Test boundary:** `services/api/app/contracts/read_models.py`, `services/api/app/contracts/audit.py`, `services/api/app/contracts/scheduler.py`
**Code boundary:** `migrations/versions/wu-031_read_models.py`, `services/api/app/contracts/read_models.py`, `services/api/app/repositories/read_models.py`, `services/api/app/services/read_models.py`, `services/api/app/tasks/read_models.py`, `services/api/tests/test_read_models.py`
**Acceptance criteria:**
- [ ] The projector consumes audit events in causal order.
- [ ] Read-model lag or worker downtime does not block authoritative write-path operations.
- [ ] Re-running the projector resumes from the last persisted cursor instead of replaying the full log.
**Pipeline phase:** Standard
**Dependencies:** WU-008A (scheduler foundation), WU-016A (audit query/correlation)
**Parallelizable with:** WU-018, WU-021, WU-024, WU-027, WU-029A, WU-030A

#### WU-032: Operational Views API

**Parent initiative:** VS-015: Cross-subsystem operational views
**Contract:**
```text
OperationalOverviewRead(open_applications, open_tickets, pending_effects, drift_count, stale_projections)
GET /api/v1/operations/overview -> OperationalOverviewRead
```
**Test boundary:** `services/api/app/contracts/read_models.py`, `services/api/app/contracts/authority.py`, `services/api/app/contracts/permissions.py`, `services/api/app/contracts/scheduler.py`
**Code boundary:** `services/api/app/contracts/read_models.py`, `services/api/app/api/v1/endpoints/operations.py`, `services/api/app/services/read_models.py`, `services/api/tests/test_operational_views.py`
**Acceptance criteria:**
- [ ] The overview reads only from projection tables and deferred-effect summaries.
- [ ] Unauthorized callers receive `403` for scoped operational views.
- [ ] Missing projections are surfaced as stale data signals rather than silent empty results.
**Pipeline phase:** Standard
**Dependencies:** WU-008B (deferred-effect summary source), WU-015A (authority enforcement guard), WU-016A (audit query surface), WU-028A (drift resolution source), WU-031 (read-model projector)
**Parallelizable with:** WU-020, WU-023a, WU-023b, WU-025A-events, WU-025B, WU-028B-discord, WU-029B-deliver

## Phase 3: Operational Depth

### VS-011: Roster Management With Role Lifecycle

#### WU-033: Roster Lifecycle API

**Parent initiative:** VS-011: Roster management with role lifecycle
**Contract:**
```text
RosterEntryCreate(chapter_id, member_id, role_id)
RosterTransitionRequest(expected_version, to_status, to_role_id?, reason)
POST /api/v1/roster-entries -> RosterEntryRead
POST /api/v1/roster-entries/{roster_entry_id}/transitions -> RosterEntryRead
GET /api/v1/roster-entries/{roster_entry_id} -> RosterEntryRead
```
**Test boundary:** `services/api/app/contracts/roster.py`, `services/api/app/contracts/base.py`
**Code boundary:** `migrations/versions/wu-033_roster.py`, `services/api/app/contracts/roster.py`, `services/api/app/repositories/roster.py`, `services/api/app/services/roster.py`, `services/api/app/api/v1/endpoints/roster.py`, `services/api/tests/test_roster.py`
**Acceptance criteria:**
- [ ] Direct roster add creates an `active` roster entry tied to a chapter role.
- [ ] Status and role transitions create a `RosterTransition` record with reason and actor attribution.
- [ ] Read with version `N`, transition with `expected_version = N`, then retry with stale `N` returns `412 Precondition Failed`.
**Pipeline phase:** Standard
**Dependencies:** WU-007C (roster foundation), WU-015A (authority enforcement guard), WU-016A (audit chain), WU-019 (chapter lifecycle API)
**Parallelizable with:** WU-035, WU-037, WU-038A

#### WU-034: Discord Roster Role Synchronization Flow

**Parent initiative:** VS-011: Roster management with role lifecycle
**Contract:**
```text
RosterSyncEvent(roster_entry_id, member_discord_user_id, chapter_role_ids, status)
RosterSyncResult(roster_entry_id, applied_role_ids, deferred_effect_id?)
handler sync_roster(event: RosterSyncEvent) -> RosterSyncResult
```
**Test boundary:** `services/discord/app/contracts/roster.py`, `services/api/app/contracts/roster.py`
**Code boundary:** `services/discord/app/contracts/roster.py`, `services/discord/app/handlers/roster.py`, `services/discord/tests/test_roster_sync.py`
**Acceptance criteria:**
- [ ] An `active` roster sync adds the configured chapter role set to the member in Discord.
- [ ] A `removed` roster sync removes the configured chapter role set from the member in Discord.
- [ ] A failed Discord role update queues a consequential deferred effect instead of silently drifting.
**Pipeline phase:** Standard
**Dependencies:** WU-008B (deferred effects), WU-009C (Discord interaction registry and dispatch), WU-010E (Discord runtime entrypoint), WU-020 (chapter provisioning flow), WU-033 (roster lifecycle API)
**Parallelizable with:** WU-036a, WU-036b, WU-038B

### VS-012: Application Interview And Waitlist Handling

#### WU-035: Application Interview And Waitlist API

**Parent initiative:** VS-012: Application interview and waitlist handling
**Contract:**
```text
ApplicationExtendedTransitionRequest(expected_version, action in ["request_interview", "waitlist", "reactivate_waitlist"], reason?, interview_thread_id?)
POST /api/v1/applications/{application_id}/interview -> ApplicationRead
POST /api/v1/applications/{application_id}/waitlist -> ApplicationRead
POST /api/v1/applications/{application_id}/reactivate -> ApplicationRead
```
**Test boundary:** `services/api/app/contracts/applications.py`, `services/api/app/contracts/base.py`
**Code boundary:** `services/api/app/contracts/applications.py`, `services/api/app/services/applications.py`, `services/api/app/api/v1/endpoints/applications/interviews.py`, `services/api/tests/test_application_interviews.py`
**Acceptance criteria:**
- [ ] `request_interview` is valid only from `in_review` and returns `state == "interview"`.
- [ ] `waitlist` is valid only from `in_review` or `interview` and returns `state == "waitlisted"`.
- [ ] `reactivate_waitlist` with current version returns `state == "claimed"`; stale version returns `412 Precondition Failed`.
**Decomposition note:** Kept as one API unit because interview and waitlist actions extend the same application state machine and versioned transition contract.
**Pipeline phase:** Standard
**Dependencies:** WU-022 (application lifecycle API), WU-029B-deliver (notification delivery worker)
**Parallelizable with:** WU-033, WU-037, WU-038A

#### WU-036a: Discord Interview Thread Flow

**Parent initiative:** VS-012: Application interview and waitlist handling
**Contract:**
```text
InterviewCommand(application_id, applicant_discord_user_id)
InterviewResultRead(application_id, interview_thread_id)
handler handle_interview(command: InterviewCommand) -> InterviewResultRead
```
**Test boundary:** `services/discord/app/contracts/application_interview.py`, `services/api/app/contracts/applications.py`
**Code boundary:** `services/discord/app/contracts/application_interview.py`, `services/discord/app/handlers/application_interview.py`, `services/discord/app/commands/application_interview.py`, `services/discord/tests/test_application_interview.py`
**Acceptance criteria:**
- [ ] Requesting an interview creates a private Discord thread and sends the resulting thread ID to the application API.
- [ ] Repeating an interview request for the same application reuses the recorded interview thread instead of creating a duplicate thread.
- [ ] A Discord thread-creation failure does not mark the application interview-ready without a successful API update.
**Pipeline phase:** Standard
**Dependencies:** WU-009C (Discord interaction registry and dispatch), WU-009D (Discord API transport), WU-010B (Discord settings), WU-010E (Discord runtime entrypoint), WU-035 (interview/waitlist API)
**Parallelizable with:** WU-034, WU-036b, WU-038B

#### WU-036b: Discord Waitlist Flow

**Parent initiative:** VS-012: Application interview and waitlist handling
**Contract:**
```text
WaitlistCommand(application_id, action in ["waitlist", "reactivate"], reason?)
WaitlistResultRead(application_id, state, review_thread_id?)
handler handle_waitlist(command: WaitlistCommand) -> WaitlistResultRead
```
**Test boundary:** `services/discord/app/contracts/application_waitlist.py`, `services/api/app/contracts/applications.py`
**Code boundary:** `services/discord/app/contracts/application_waitlist.py`, `services/discord/app/handlers/application_waitlist.py`, `services/discord/app/commands/application_waitlist.py`, `services/discord/tests/test_application_waitlist.py`
**Acceptance criteria:**
- [ ] Waitlisting an application posts a single applicant-facing status update tied to the application ID.
- [ ] Reactivating a waitlisted application reuses or re-establishes the review thread without duplicating the application record.
- [ ] API conflict or validation failures do not duplicate Discord status messages for the same application.
**Pipeline phase:** Standard
**Dependencies:** WU-009C (Discord interaction registry and dispatch), WU-009D (Discord API transport), WU-010B (Discord settings), WU-010E (Discord runtime entrypoint), WU-035 (interview/waitlist API)
**Parallelizable with:** WU-034, WU-036a, WU-038B

### VS-013: SLA Enforcement For Tickets

#### WU-037: Ticket SLA Evaluator And Escalation Worker

**Parent initiative:** VS-013: SLA enforcement for tickets
**Contract:**
```text
SlaThresholdRead(elapsed, consequence in ["notify_owner", "notify_scope", "flag_for_review", "auto_escalate"])
SlaTriggerRead(ticket_id, threshold, applied_at)
scheduled handler evaluate_ticket_sla() -> list[SlaTriggerRead]
```
**Test boundary:** `services/api/app/contracts/tickets.py`, `services/api/app/contracts/scheduler.py`, `services/api/app/contracts/notifications.py`
**Code boundary:** `services/api/app/contracts/tickets.py`, `services/api/app/services/tickets.py`, `services/api/app/tasks/ticket_sla.py`, `services/api/tests/test_ticket_sla.py`
**Acceptance criteria:**
- [ ] Thresholds fire in ascending elapsed-time order and never skip earlier configured consequences.
- [ ] `auto_escalate` follows the ticket category's configured escalation path; if none exists, the ticket is flagged for review instead.
- [ ] Re-running the SLA worker does not duplicate an already-applied threshold for the same ticket.
**Decomposition note:** Kept as one worker unit because SLA evaluation and escalation are one scheduled enforcement loop over the same ticket threshold contract.
**Pipeline phase:** Standard
**Dependencies:** WU-008A (scheduler foundation), WU-025A-create (ticket creation API), WU-025B (ticket transition API), WU-029B-deliver (notification delivery worker)
**Parallelizable with:** WU-033, WU-035, WU-038A

### VS-014: Temporary Permission Management

#### WU-038A: Temporary Permission Renewal API

**Parent initiative:** VS-014: Temporary permission management
**Contract:**
```text
PermissionIntentRenewRequest(expected_version, expires_at, reason)
POST /api/v1/permission-intents/{intent_id}/renew -> PermissionIntentRead
```
**Test boundary:** `services/api/app/contracts/permissions.py`, `services/api/app/contracts/base.py`
**Code boundary:** `services/api/app/contracts/permissions.py`, `services/api/app/services/permissions.py`, `services/api/app/api/v1/endpoints/permissions/temporary.py`, `services/api/tests/test_permission_temporary_api.py`
**Acceptance criteria:**
- [ ] Renewing a temporary intent with current version updates `expires_at`.
- [ ] Renewing with stale version returns `412 Precondition Failed`.
- [ ] Renewal is rejected for non-temporary intents.
**Pipeline phase:** Standard
**Dependencies:** WU-015A (authority enforcement guard), WU-016A (audit chain), WU-027 (permission-intent API), WU-028A (drift resolution API)
**Parallelizable with:** WU-033, WU-035, WU-037

#### WU-038B: Temporary Permission Expiry Worker

**Parent initiative:** VS-014: Temporary permission management
**Contract:**
```text
POST /api/v1/permission-intents/expire/run
scheduled handler expire_temporary_permission_intents() -> list[PermissionDriftRead]
```
**Test boundary:** `services/api/app/contracts/permissions.py`, `services/api/app/contracts/scheduler.py`
**Code boundary:** `services/api/app/contracts/permissions.py`, `services/api/app/contracts/scheduler.py`, `services/api/app/tasks/permission_expiry.py`, `services/api/app/services/permissions.py`, `services/api/tests/test_permission_temporary_worker.py`
**Acceptance criteria:**
- [ ] The expiry worker creates drift entries for temporary intents whose `expires_at` has passed.
- [ ] Re-running the worker does not duplicate drift rows for the same expired intent state.
- [ ] Expired temporary intents flow through the stable reconciliation adapter rather than mutating Discord-managed state inline.
**Pipeline phase:** Standard
**Dependencies:** WU-008A (scheduler foundation), WU-028B-discord (permission reconciliation adapter), WU-029B-deliver (notification delivery worker), WU-038A (temporary renewal API)
**Parallelizable with:** WU-034, WU-036a, WU-036b

## Phase 4: Operational Maturity

### VS-016: Compliance Rule Evaluation With Evidence

#### WU-039: Compliance Rule Management API

**Parent initiative:** VS-016: Compliance rule evaluation with evidence
**Contract:**
```text
ComplianceRuleCreate(chapter_id, name, cadence, evidence_requirements, consequence_policy)
ComplianceRuleRead(id, chapter_id, name, cadence, evidence_requirements, consequence_policy, version)
POST /api/v1/compliance/rules -> ComplianceRuleRead
PATCH /api/v1/compliance/rules/{rule_id} -> ComplianceRuleRead
```
**Test boundary:** `services/api/app/contracts/compliance.py`, `services/api/app/contracts/base.py`
**Code boundary:** `migrations/versions/wu-039_compliance_rules.py`, `services/api/app/contracts/compliance.py`, `services/api/app/repositories/compliance.py`, `services/api/app/services/compliance.py`, `services/api/app/api/v1/endpoints/compliance/rules.py`, `services/api/tests/test_compliance_rules.py`
**Acceptance criteria:**
- [ ] Creating a rule persists cadence, evidence requirements, and consequence policy.
- [ ] Updating a rule with current version succeeds; stale version returns `412 Precondition Failed`.
- [ ] Rules remain chapter-scoped and cannot be reassigned across chapters by update.
**Pipeline phase:** Standard
**Dependencies:** WU-017 (runtime dependency: preview-confirm operating model for compliance-rule updates; does not consume policy contract types), WU-019 (chapter lifecycle API), WU-015A (authority enforcement guard)
**Parallelizable with:** WU-042

#### WU-040A: Evidence Submission API

**Parent initiative:** VS-016: Compliance rule evaluation with evidence
**Contract:**
```text
EvidenceSubmissionCreate(member_id, chapter_id, rule_id, attachment_ref, submitted_at)
EvidenceSubmissionRead(id, member_id, chapter_id, rule_id, attachment_ref, ocr_status in ["pending", "complete", "failed"], version)
POST /api/v1/compliance/evidence -> EvidenceSubmissionRead
GET /api/v1/compliance/evidence/{evidence_id} -> EvidenceSubmissionRead
```
**Test boundary:** `services/api/app/contracts/compliance.py`, `services/api/app/contracts/base.py`
**Code boundary:** `migrations/versions/wu-040a_compliance_evidence.py`, `services/api/app/contracts/compliance.py`, `services/api/app/repositories/compliance.py`, `services/api/app/services/compliance.py`, `services/api/app/api/v1/endpoints/compliance/evidence.py`, `services/api/tests/test_compliance_evidence.py`
**Acceptance criteria:**
- [ ] Evidence submission persists the attachment reference before OCR extraction completes.
- [ ] Newly created evidence reads return `ocr_status == "pending"` until extraction runs.
- [ ] Submitting evidence for an unknown member, chapter, or rule returns the contract-defined error response and writes no evidence row.
**Pipeline phase:** Deep
**Dependencies:** WU-011 (member aggregate), WU-019 (chapter lifecycle API), WU-039 (compliance rules)
**Parallelizable with:** WU-042, WU-043A, WU-044A

#### WU-040B-extract: OCR Extraction API

**Parent initiative:** VS-016: Compliance rule evaluation with evidence
**Contract:**
```text
EvidenceExtractionRead(evidence_id, ocr_text?, extracted_fields?, status in ["pending", "complete", "failed"], version)
POST /api/v1/compliance/evidence/{evidence_id}/extract -> EvidenceExtractionRead
```
**Test boundary:** `services/api/app/contracts/compliance_extraction.py`, `services/api/app/contracts/base.py`
**Code boundary:** `services/api/app/contracts/compliance_extraction.py`, `services/api/app/infrastructure/ocr.py`, `services/api/app/services/compliance_extraction.py`, `services/api/app/api/v1/endpoints/compliance/evidence_extract.py`, `services/api/tests/test_compliance_ocr_extract.py`
**Acceptance criteria:**
- [ ] OCR extraction stores extracted text and structured fields on the existing evidence record.
- [ ] Extraction failure sets `status == "failed"` while preserving the submitted evidence row for retry.
- [ ] Re-running extraction for unchanged evidence returns the persisted extraction view without creating a duplicate evidence row.
**Pipeline phase:** Deep
**Dependencies:** WU-010C (API factory and liveness substrate), WU-040A (evidence submission API)
**Parallelizable with:** WU-040B-correct, WU-041A, WU-043B, WU-044B

#### WU-040B-correct: Officer Correction API

**Parent initiative:** VS-016: Compliance rule evaluation with evidence
**Contract:**
```text
OfficerCorrectionRequest(expected_version, corrected_fields, reason)
OfficerCorrectionRead(evidence_id, extracted_fields, corrected_by, corrected_at, version)
POST /api/v1/compliance/evidence/{evidence_id}/correct -> OfficerCorrectionRead
```
**Test boundary:** `services/api/app/contracts/compliance_corrections.py`, `services/api/app/contracts/base.py`
**Code boundary:** `services/api/app/contracts/compliance_corrections.py`, `services/api/app/services/compliance_corrections.py`, `services/api/app/api/v1/endpoints/compliance/evidence_correct.py`, `services/api/tests/test_compliance_ocr_correct.py`
**Acceptance criteria:**
- [ ] Officer correction with current version updates extracted fields and returns a typed correction response.
- [ ] Officer correction with stale version returns `412 Precondition Failed`.
- [ ] Officer correction does not mutate the raw attachment reference or OCR raw text captured on the evidence record.
**Pipeline phase:** Standard
**Dependencies:** WU-015A (authority enforcement guard), WU-016A (audit chain), WU-040A (evidence submission API)
**Parallelizable with:** WU-040B-extract, WU-041A, WU-043B, WU-044B

#### WU-041A: Compliance Evaluation Review API

**Parent initiative:** VS-016: Compliance rule evaluation with evidence
**Contract:**
```text
ComplianceEvaluationRead(id, member_id, chapter_id, rule_id, rule_version, result in ["compliant", "violation", "insufficient_evidence"], consequence_applied?)
ComplianceEvaluationReviewRequest(expected_version, action in ["confirm", "override", "request_evidence"], reason)
GET /api/v1/compliance/evaluations/{evaluation_id} -> ComplianceEvaluationRead
POST /api/v1/compliance/evaluations/{evaluation_id}/review -> ComplianceEvaluationRead
```
**Test boundary:** `services/api/app/contracts/compliance.py`, `services/api/app/contracts/base.py`, `services/api/app/contracts/roster.py`
**Code boundary:** `migrations/versions/wu-041a_compliance_review_api.py`, `services/api/app/contracts/compliance.py`, `services/api/app/repositories/compliance.py`, `services/api/app/services/compliance_review.py`, `services/api/app/api/v1/endpoints/compliance/evaluations.py`, `services/api/tests/test_compliance_review_api.py`
**Acceptance criteria:**
- [ ] Reviewing an evaluation with stale version returns `412 Precondition Failed`.
- [ ] `override` requires a reason and records an audit entry.
- [ ] `request_evidence` returns the evaluation to a reviewable state without deleting prior evidence links.
**Pipeline phase:** Standard
**Dependencies:** WU-015A (authority enforcement guard), WU-016A (audit chain), WU-033 (roster lifecycle API), WU-039 (compliance rules), WU-040A (evidence submission API)
**Parallelizable with:** WU-040B-extract, WU-040B-correct, WU-043B, WU-044B

#### WU-041B: Scheduled Compliance Evaluation Worker

**Parent initiative:** VS-016: Compliance rule evaluation with evidence
**Contract:**
```text
POST /api/v1/compliance/evaluations/run
scheduled handler run_compliance_evaluations() -> list[ComplianceEvaluationRead]
```
**Test boundary:** `services/api/app/contracts/compliance.py`, `services/api/app/contracts/scheduler.py`, `services/api/app/contracts/roster.py`
**Code boundary:** `services/api/app/tasks/compliance.py`, `services/api/app/services/compliance.py`, `services/api/tests/test_compliance_evaluation_worker.py`
**Acceptance criteria:**
- [ ] A scheduled run evaluates every `active` roster member against active rules for the requested period and pins `rule_version`.
- [ ] A `flag_for_review` or `auto_probation` result moves the roster entry to `under_review` through the roster API path.
- [ ] Re-running the worker does not create duplicate evaluations for the same member, rule, and period.
**Pipeline phase:** Deep
**Dependencies:** WU-008A (scheduler foundation), WU-029B-deliver (notification delivery worker), WU-033 (roster lifecycle API), WU-039 (compliance rules), WU-040B-extract (OCR extraction API), WU-041A (evaluation review API)
**Parallelizable with:** WU-045A-applications, WU-045A-tickets

### VS-017: Chapter Governance Lifecycle

#### WU-042: Chapter Governance Lifecycle API

**Parent initiative:** VS-017: Chapter governance lifecycle
**Contract:**
```text
ChapterGovernanceTransitionRequest(expected_version, to_state in ["probation", "active", "archiving", "archived"], reason)
POST /api/v1/chapters/{chapter_id}/governance-transitions -> ChapterRead
GET /api/v1/chapters/{chapter_id}/archive-status
```
**Test boundary:** `services/api/app/contracts/chapters.py`, `services/api/app/contracts/base.py`
**Code boundary:** `services/api/app/contracts/chapters.py`, `services/api/app/services/chapters.py`, `services/api/app/api/v1/endpoints/chapters/governance.py`, `services/api/tests/test_chapter_governance.py`
**Acceptance criteria:**
- [ ] `active -> probation -> active` succeeds only with current version and a non-empty reason.
- [ ] `active` or `probation -> archiving` succeeds only when initiated by an authorized actor.
- [ ] Attempting to mark a chapter `archived` before archive prerequisites are satisfied returns `409 Conflict`.
**Pipeline phase:** Standard
**Dependencies:** WU-019 (chapter lifecycle API), WU-015A (authority enforcement guard), WU-016A (audit chain)
**Parallelizable with:** WU-039, WU-040A

#### WU-043A: Chapter Archive Plan API

**Parent initiative:** VS-017: Chapter governance lifecycle
**Contract:**
```text
ChapterArchivePlanRead(chapter_id, pending_application_ids, open_ticket_ids, authority_grant_ids, unresolved_effect_ids)
GET /api/v1/chapters/{chapter_id}/archive-plan -> ChapterArchivePlanRead
```
**Test boundary:** `services/api/app/contracts/chapters.py`, `services/api/app/contracts/scheduler.py`, `services/api/app/contracts/applications.py`, `services/api/app/contracts/tickets.py`
**Code boundary:** `services/api/app/contracts/chapters.py`, `services/api/app/services/chapters.py`, `services/api/app/api/v1/endpoints/chapters/archive.py`, `services/api/tests/test_chapter_archive_plan.py`
**Acceptance criteria:**
- [ ] Archive-plan output enumerates pending applications, open tickets, active grants, and queued consequential effects for the chapter.
- [ ] The plan is read-only and does not transfer or close any dependency.
- [ ] The plan includes enough identity to support a later execution request without re-deriving member or ticket ownership locally.
**Pipeline phase:** Standard
**Dependencies:** WU-008B (deferred-effect foundation), WU-022 (application lifecycle API), WU-025A-create (ticket creation API), WU-025B (ticket transition API), WU-042 (chapter governance lifecycle)
**Parallelizable with:** WU-040A, WU-044A

#### WU-043B: Chapter Archive Execution Worker

**Parent initiative:** VS-017: Chapter governance lifecycle
**Contract:**
```text
ChapterArchiveExecuteRequest(transfer_scope_map, reason)
POST /api/v1/chapters/{chapter_id}/archive-execute
```
**Test boundary:** `services/api/app/contracts/chapters.py`, `services/api/app/contracts/scheduler.py`, `services/api/app/contracts/applications.py`, `services/api/app/contracts/tickets.py`
**Code boundary:** `services/api/app/contracts/chapters.py`, `services/api/app/tasks/archive.py`, `services/api/app/services/chapters.py`, `services/api/tests/test_chapter_archive_execution.py`
**Acceptance criteria:**
- [ ] Executing the archive plan transfers or closes each listed dependency under a shared correlation ID.
- [ ] Any dependency whose preconditions changed after the plan was generated is surfaced as stale deferred work rather than executed blindly.
- [ ] Re-running execution after completion is idempotent and does not duplicate closures or transfers.
**Pipeline phase:** Deep
**Dependencies:** WU-008B (deferred-effect foundation), WU-022 (application lifecycle API), WU-025A-create (ticket creation API), WU-025B (ticket transition API), WU-043A (archive-plan API)
**Parallelizable with:** WU-040B-extract, WU-040B-correct, WU-041A, WU-044B

### VS-018: Leadership Succession With Context Transfer

#### WU-044A: Succession Plan API

**Parent initiative:** VS-018: Leadership succession with context transfer
**Contract:**
```text
SuccessionPlanRead(predecessor_grant_id, successor_member_id?, pending_ticket_ids, pending_application_ids)
GET /api/v1/chapters/{chapter_id}/succession-plan -> SuccessionPlanRead
```
**Test boundary:** `services/api/app/contracts/authority.py`, `services/api/app/contracts/roster.py`, `services/api/app/contracts/applications.py`, `services/api/app/contracts/tickets.py`
**Code boundary:** `services/api/app/contracts/authority.py`, `services/api/app/services/authority.py`, `services/api/app/api/v1/endpoints/authority/succession_plan.py`, `services/api/tests/test_succession_plan.py`
**Acceptance criteria:**
- [ ] A chapter role marked `triggers_succession == true` produces a succession plan when the incumbent departs.
- [ ] If no successor is designated, the plan remains queryable and no automatic authority transfer occurs.
- [ ] The plan enumerates pending applications and tickets without transferring ownership.
**Pipeline phase:** Standard
**Dependencies:** WU-014 (authority grant API), WU-022 (application lifecycle API), WU-025A-create (ticket creation API), WU-025B (ticket transition API), WU-033 (roster lifecycle API), WU-042 (chapter governance lifecycle)
**Parallelizable with:** WU-040A, WU-043A

#### WU-044B: Authority Transfer API

**Parent initiative:** VS-018: Leadership succession with context transfer
**Contract:**
```text
AuthorityTransferRequest(predecessor_grant_id, successor_member_id, reason)
POST /api/v1/authority-grants/{grant_id}/transfer -> AuthorityGrantRead
```
**Test boundary:** `services/api/app/contracts/authority.py`, `services/api/app/contracts/roster.py`
**Code boundary:** `services/api/app/contracts/authority.py`, `services/api/app/services/authority.py`, `services/api/app/api/v1/endpoints/authority/transfer.py`, `services/api/tests/test_authority_transfer.py`
**Acceptance criteria:**
- [ ] Transferring authority creates a new grant whose `predecessor_grant_id` points to the departing grant.
- [ ] Transfer is rejected when no eligible successor is designated in the active succession plan.
- [ ] Transfer writes reuse the existing grant lifecycle path and do not bypass audit attribution.
**Pipeline phase:** Standard
**Dependencies:** WU-014 (authority grant API), WU-033 (roster lifecycle API), WU-042 (chapter governance lifecycle), WU-044A (succession plan API)
**Parallelizable with:** WU-040B-extract, WU-040B-correct, WU-041A, WU-043B

#### WU-045A-applications: Pending Application Handoff Execution

**Parent initiative:** VS-018: Leadership succession with context transfer
**Contract:**
```text
ApplicationHandoffExecuteRequest(reason)
ApplicationHandoffRead(grant_id, application_ids, transferred_ids, flagged_ids)
POST /api/v1/authority-grants/{grant_id}/handoff/applications -> ApplicationHandoffRead
```
**Test boundary:** `services/api/app/contracts/authority.py`, `services/api/app/contracts/applications.py`
**Code boundary:** `services/api/app/contracts/applications.py`, `services/api/app/services/leadership_handoff_applications.py`, `services/api/app/api/v1/endpoints/authority/handoff_applications.py`, `services/api/tests/test_leadership_handoff_applications.py`
**Acceptance criteria:**
- [ ] Executing application handoff transfers pending applications to the successor or flags each blocked application individually.
- [ ] The handoff writes a causal audit chain linking predecessor departure, grant transfer, and each application handoff.
- [ ] Application handoff is idempotent and does not duplicate reassignment when retried.
**Pipeline phase:** Standard
**Dependencies:** WU-016A (audit chain), WU-022 (application lifecycle API), WU-044B (authority transfer API)
**Parallelizable with:** WU-041B, WU-045A-tickets

#### WU-045A-tickets: Pending Ticket Handoff Execution

**Parent initiative:** VS-018: Leadership succession with context transfer
**Contract:**
```text
TicketHandoffExecuteRequest(reason)
TicketHandoffRead(grant_id, ticket_ids, transferred_ids, flagged_ids)
POST /api/v1/authority-grants/{grant_id}/handoff/tickets -> TicketHandoffRead
```
**Test boundary:** `services/api/app/contracts/authority.py`, `services/api/app/contracts/tickets.py`
**Code boundary:** `services/api/app/contracts/tickets.py`, `services/api/app/services/leadership_handoff_tickets.py`, `services/api/app/api/v1/endpoints/authority/handoff_tickets.py`, `services/api/tests/test_leadership_handoff_tickets.py`
**Acceptance criteria:**
- [ ] Executing ticket handoff transfers pending tickets to the successor or flags each blocked ticket individually.
- [ ] The handoff writes a causal audit chain linking predecessor departure, grant transfer, and each ticket handoff.
- [ ] Ticket handoff is idempotent and does not duplicate reassignment when retried.
**Pipeline phase:** Standard
**Dependencies:** WU-016A (audit chain), WU-025A-create (ticket creation API), WU-025B (ticket transition API), WU-044B (authority transfer API)
**Parallelizable with:** WU-041B, WU-045A-applications

#### WU-045B: Leadership Context View API

**Parent initiative:** VS-018: Leadership succession with context transfer
**Contract:**
```text
LeadershipContextRead(member_id, inherited_grant_id, pending_application_ids, pending_ticket_ids, flagged_items)
GET /api/v1/members/{member_id}/leadership-context -> LeadershipContextRead
```
**Test boundary:** `services/api/app/contracts/read_models.py`, `services/api/app/contracts/authority.py`, `services/api/app/contracts/applications.py`, `services/api/app/contracts/tickets.py`
**Code boundary:** `services/api/app/contracts/read_models.py`, `services/api/app/services/read_models.py`, `services/api/app/api/v1/endpoints/authority/leadership_context.py`, `services/api/tests/test_leadership_context.py`
**Acceptance criteria:**
- [ ] `GET /api/v1/members/{member_id}/leadership-context` returns the successor's inherited open work set after handoff completes.
- [ ] The view reads from projection state rather than re-deriving ownership directly from command handlers.
- [ ] Missing handoff state is surfaced as an explicit stale-context signal rather than silent empty results.
**Pipeline phase:** Standard
**Dependencies:** WU-031 (read-model pipeline), WU-044B (authority transfer API), WU-045A-applications (application handoff execution), WU-045A-tickets (ticket handoff execution)
**Parallelizable with:** none

## Dependency Graph

Topological order, with same-line items safe to start together:

```text
Foundation cohorts:
[WU-001 + WU-009A + WU-009B]
  ->
[WU-002 + WU-010A + WU-010B]
  ->
[WU-003 + WU-010C]
  ->
[WU-003B + WU-004 + WU-005 + WU-006A + WU-007A + WU-007B + WU-008A + WU-009C + WU-009D + WU-010D + WU-010E]
  ->
[WU-006B + WU-007C + WU-008B]

Phase-1 cohorts:
[WU-011 + WU-014]
  ->
[WU-012 + WU-015A]
  ->
[WU-013 + WU-015B + WU-016A]
  ->
[WU-016B + WU-017]

Phase-2 cohorts:
[WU-018 + WU-021 + WU-024 + WU-027 + WU-029A + WU-030A + WU-031]
  ->
[WU-019 + WU-022 + WU-025A-create + WU-028A + WU-029B-materialize + WU-030B]
  ->
[WU-028B-api]
  ->
[WU-020 + WU-023a + WU-023b + WU-025A-events + WU-025B + WU-028B-discord + WU-029B-deliver + WU-032]
  ->
[WU-025C + WU-026 + WU-029C]

Phase-3 cohorts:
[WU-033 + WU-035 + WU-037 + WU-038A]
  ->
[WU-034 + WU-036a + WU-036b + WU-038B]

Phase-4 cohorts:
[WU-039 + WU-042]
  ->
[WU-040A + WU-043A + WU-044A]
  ->
[WU-040B-extract + WU-040B-correct + WU-041A + WU-043B + WU-044B]
  ->
[WU-041B + WU-045A-applications + WU-045A-tickets]
  ->
[WU-045B]
```

## Critical Path

The longest gated chain, including mandatory phase boundaries, is:

`WU-001 -> WU-002 -> WU-003 -> WU-008A -> WU-008B -> WU-014 -> WU-015A -> WU-016A -> WU-017 -> WU-024 -> WU-025A-create -> WU-025B -> WU-025C -> WU-033 -> WU-034 -> WU-039 -> WU-040A -> WU-041A -> WU-041B`

Why this is the critical path:

- It includes the longest Phase 0 foundation chain because Phase 1 cannot begin until deferred-effect and degradation substrate work is complete.
- It carries governance control surfaces through ticket creation, initial message-event separation, transition, and append-only messaging before the ticket-dependent maturity slices can rely on them.
- It includes the longest Phase 3 gated pair because the roadmap's phase boundary holds Phase 4 until the roster synchronization cohort completes after `WU-033`.
- It blocks the compliance worker behind rule management, evidence submission, and evaluation review, while the OCR extraction and officer correction units now run in parallel instead of living inside the same work unit.

## Parallelization Map

Alembic reconciliation rule for every cohort below:

- If a cohort contains multiple migration-writing work units, the next cohort does not start a new migration-writing unit until the parallel heads are collapsed into one Alembic merge revision.
- That merge step is an acceptance criterion of the first started migration-writing work unit in the next cohort, or a short pre-cohort reconciliation task when the next cohort is otherwise migration-free.

| Phase | Parallel groups | Max concurrent worktrees |
|---|---|---|
| 0 | `[WU-001 + WU-009A + WU-009B]`, `[WU-002 + WU-010A + WU-010B]`, `[WU-003 + WU-010C]`, `[WU-003B + WU-004 + WU-005 + WU-006A + WU-007A + WU-007B + WU-008A + WU-009C + WU-009D + WU-010D + WU-010E]`, `[WU-006B + WU-007C + WU-008B]` | `3`, `3`, `2`, `11`, `3` |
| 1 | `[WU-011 + WU-014]`, `[WU-012 + WU-015A]`, `[WU-013 + WU-015B + WU-016A]`, `[WU-016B + WU-017]` | `2`, `2`, `3`, `2` |
| 2 | `[WU-018 + WU-021 + WU-024 + WU-027 + WU-029A + WU-030A + WU-031]`, `[WU-019 + WU-022 + WU-025A-create + WU-028A + WU-029B-materialize + WU-030B]`, `[WU-028B-api]`, `[WU-020 + WU-023a + WU-023b + WU-025A-events + WU-025B + WU-028B-discord + WU-029B-deliver + WU-032]`, `[WU-025C + WU-026 + WU-029C]` | `7`, `6`, `1`, `8`, `3` |
| 3 | `[WU-033 + WU-035 + WU-037 + WU-038A]`, `[WU-034 + WU-036a + WU-036b + WU-038B]` | `4`, `4` |
| 4 | `[WU-039 + WU-042]`, `[WU-040A + WU-043A + WU-044A]`, `[WU-040B-extract + WU-040B-correct + WU-041A + WU-043B + WU-044B]`, `[WU-041B + WU-045A-applications + WU-045A-tickets]`, `[WU-045B]` | `2`, `3`, `5`, `3`, `1` |

## Summary

| Metric | Value |
|---|---|
| Total work units | `78` |
| Total roadmap phases | `5` |
| Critical path length | `19 work units` |
| Maximum parallelization | `11 concurrent worktrees` |
