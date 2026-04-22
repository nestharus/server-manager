# Architecture Notes

Reference for foundational patterns in the server-manager codebase. See `AGENTS.md` for workflow and policy; this doc covers how the code is shaped.

## mutate_entity - the mutation substrate
- Location: `services/api/app/services/mutations.py`
- Signature:

```python
def mutate_entity(
    *,
    db: PostgresDatabase,
    aggregate_type: str,
    aggregate_id: str,
    request: MutationRequest,
    action_type: str,
    action_payload: dict[str, object],
    payload_allowlist: set[str] | None,
    mutate_projection: Callable[[Connection[Any]], StateChangeDraft],
    scope_kind: ScopeKind | None = None,
    scope_id: str | None = None,
    connection: Connection[Any] | None = None,
) -> MutationResult
```

- Purpose: every durable aggregate mutation writes audit action rows, state-change rows, and the aggregate head through one primitive.
- `request` owns `expected_version`, actor identity, request surface, and optional correlation/causation ids.
- `scope_kind` and `scope_id` are audit metadata for the action row; they do not replace aggregate identity.
- `action_payload` is the full candidate request payload; `payload_allowlist` decides what is persisted into `activity_actions.request_json`.
- `payload_allowlist=None` or an empty set means audit request payload is redacted to `{}`.
- `request.expected_version == 0` is the bootstrap path: `aggregate_heads` is inserted with `ON CONFLICT DO NOTHING` before the head lock/read.
- `mutate_projection(connection)` performs the domain write and returns the `StateChangeDraft`.
- Accepted, rejected, and failed outcomes all write `activity_actions` rows; failures are logged in a separate transaction.
- Rejected OCC writes still emit an audit action with `status="rejected"` and the expected/current version pair in `reason_text`.
- If `request.correlation_id` is absent, the primitive requires an ambient audit context; otherwise it raises `MissingCorrelationContextError`.
- Common API mapping: `StaleMutationError` becomes `412 Precondition Failed`; `MissingAggregateError` becomes not found; projection writes can still raise repository exceptions such as `UniqueViolation`.
- Use `connection=` when multiple writes must commit or roll back together, or when a caller already holds the transaction.
- Do not pass `connection=` for ordinary single-aggregate mutations; let `mutate_entity` own its transaction boundary.

## Router / endpoint subpackages
- Location: `services/api/app/api/v1/router.py`
- The top-level router aggregates endpoint modules for `applications`, `audit`, `authority`, `chapter_templates`, `chapters`, `compliance`, `health`, `members`, `notifications`, `operations`, `permissions`, `policies`, `ready`, `roster`, `system`, `tickets`, and `trust`.
- Subpackage pattern: a directory-level `__init__.py` re-exports a composed router.
- Current examples:
  - `services/api/app/api/v1/endpoints/authority/__init__.py`
  - `services/api/app/api/v1/endpoints/tickets/__init__.py`
- Use a subpackage when one API surface needs multiple modules, shared error helpers, or stacked PR decomposition without turning one file into a grab bag.
- Subpackages usually carry a local `_shared.py` for error mapping or ETag parsing so the surface stays cohesive without cross-package imports.
- Keep the top-level `router.py` importing the subpackage once; internal module churn stays inside the subpackage.
- PR decomposition rule: register only the routers that ship in that PR. Later routers belong in later stacked PRs, not behind dormant imports.

## Migration chain
- Location: `migrations/versions/`
- Naming pattern: files use `wu-NNN_<name>.py`; revisions use `wu_NNN_<name>` strings with explicit `down_revision`.
- Current head by revision graph: `wu_041a_compliance_evaluations`.
- Current tail: `wu_042_chapter_governance -> wu_035_application_interview -> wu_027_perm_intent_refinements -> wu_028a_perm_drift_widening -> wu_028b_perm_reconciliation_runs -> wu_031_read_models -> wu_038_permission_intent_expiry -> wu_039_compliance_rules -> wu_040a_compliance_evidence -> wu_041a_compliance_evaluations`.
- Read migrations as a pinned chain, not as independent feature files.
- New migrations should pin `down_revision` to the immediately previous head; do not create side heads casually.
- Service-actor seed migrations use exact-match guards:
  - `permissions @> ... AND permissions <@ ...`
  - `revoked_at IS NULL`
  - usually `expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP`
- Later seed migrations such as `wu_031` and `wu_041a` use a no-op downgrade with a Live Server Principle comment.
- `read_model_cursors` rows are seeded in migrations only; runtime code treats a missing row as an error, not a bootstrap opportunity.

## authority_grants / authority checks
- Schema comes from `wu-004_authority_foundation.py` plus `wu-014_authority_api.py`.
- Current columns:
  - `id`
  - `grantee_id`
  - `scope_kind`
  - `scope_id`
  - `permissions`
  - `expires_at`
  - `revoked_at`
  - `predecessor_grant_id`
  - `created_at`
  - `revoked_by`
  - `revocation_reason`
- Key constraints:
  - `scope_kind IN ('global', 'chapter', 'member')`
  - revocation trio stays in lockstep via `authority_grants_revocation_trio_check`
  - predecessor cannot self-reference
- Active-grant lookups should treat `permissions` as a set and use exact-match containment, not subset-only matching.
- Scope evaluation is exact, not hierarchical:
  - `grant.scope_kind` must equal `requirement.scope_kind`
  - if a grant has non-null `scope_id`, it must equal the required `scope_id`
- `_require_scoped_authority()` merges actor aliases before evaluating grants, so a member's Discord ID and member UUID both participate in the check.
- Grant seeding should use exact permission-set matching to avoid superset false positives.

## Discord handler pattern
- Interaction handlers receive `ack_deferred` on the envelope and should call it before the first slow API or Discord operation.
- Tests assert ack-before-API ordering for long-running handlers such as chapter provisioning.
- API calls always send explicit actor headers.
- Bot-owned automation uses service headers such as:
  - `discord-provisioner`
  - `roster-syncer`
  - `member-onboarder`
- User-driven flows can use user headers directly when the API mutation is truly user-owned, for example ticket creation/transition and some application submission paths.
- When a Discord adapter uses service authority but must preserve the originating user, keep the service actor in headers and place the user attribution in the request body.
- Current request-body fields vary by subsystem:
  - generic `originating_actor_kind` / `originating_actor_id`
  - chapter workflows also materialize `originating_user_discord_id`
- Discord nonces must fit 25 characters; current handlers derive them from UUID bytes via base32, trim `=`, then slice to 25.
- Seed required service-actor grants in the migration that introduces the workflow, not lazily in runtime code.

## Test infrastructure
- API fixtures live in `services/api/tests/conftest.py`.
- Primary fixtures:
  - `fresh_migrated_postgres_db`
  - `governance_dsn`
  - `governance_db`
  - `migrated_postgres_db`
- `fresh_migrated_postgres_db` is the clean-schema fixture; `governance_db` is the service-facing `PostgresDatabase` handle layered on top of the per-test DSN.
- `GOVERNANCE_TABLES` is the source of truth for per-test cleanup; every new aggregate or governance table must be added there.
- `reset_governance_state()` truncates only tables that exist in the current schema, so tests stay branch-safe.
- After truncation, `conftest.py` re-seeds:
  - `read_model_cursors('operational_overview')`
  - `read-model-projector`
  - `compliance-evaluator`
- Discord tests use lightweight fakes instead of deep mocks when behavior matters:
  - `MockGuild`
  - `FakeApiClient`
  - `InteractionEnvelope` helpers with optional `ack_deferred`
- Grep-invariant tests enforce legacy removals in place; see `AGENTS.md` section `No Backwards Compatibility`.
- Common commands:
  - `cd services/api && uv run pytest tests/ -q`
  - `cd services/discord && uv run pytest tests/ -q`

## Read-model cursor design
- Read-model logic lives in `services/api/app/services/read_models.py` and `services/api/app/repositories/read_models.py`.
- `activity_state_changes.id` is treated as a resumable monotonic cursor, but visibility is fenced by age.
- `MIN_AGE_SECONDS = 5` is applied in two places:
  - when the projector advances `read_model_cursors`
  - when reads compute the visible settled head
- Use the same fence on both sides; mismatched fences make a healthy projector look stale under sustained write load.
- `read_model_cursors` holds one row per projection; current projection name is `operational_overview`.
- Missing cursor rows raise `CursorNotSeededError`; API surfaces map that to `503`, not auto-seed.
- Cursor advancement is OCC-guarded with `expected_version=cursor.version`.
- `StaleMutationError` from concurrent projector ticks is expected control flow and should be logged at debug level.
- `is_stale` is a projector-liveness signal, not a count-freshness signal.
- Current staleness rules:
  - stale by lag if `cursor_lag_events > 100`
  - stale by time only if `cursor_lag_events > 0` and the last processed timestamp is older than 5 minutes

## Excluded (stale relative to current code)
- Handoff `mutate_entity` signature is stale: current code passes a `MutationRequest` plus `action_payload`; it no longer takes top-level `expected_version` and actor parameters.
- Handoff scope hierarchy claim (`global > chapter > member`) is stale: current `services/api/app/services/authority.py::evaluate()` requires exact `scope_kind` equality.
- Handoff treated `wu-029a` as the reference for no-op grant-seed downgrades; current `wu-029a_notifications.py` still deletes the seeded grant on downgrade.
- Handoff phrased Discord API calls as uniformly service-authenticated; current adapters use both service headers and user headers depending on who owns the mutation.
