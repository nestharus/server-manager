from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from psycopg import Connection, errors

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.authority import AuthorityDecisionRead, AuthorityRequirement
from app.contracts.chapter_templates import (
    CURRENT_TEMPLATE_SCHEMA_VERSION,
    ChapterTemplateNotFoundError,
    TemplateSchemaVersionMismatchError,
)
from app.contracts.chapters import (
    ChapterArchiveBlockerRead,
    ChapterArchiveExecuteRequest,
    ChapterArchiveInProgressError,
    ChapterArchivePlanRead,
    ChapterArchivePlanSectionRead,
    ChapterArchivePrerequisitesError,
    ChapterArchiveStatusRead,
    ChapterCreate,
    ChapterDiscordResources,
    ChapterDuplicateNameError,
    ChapterGovernanceTransitionRequest,
    ChapterNotFoundError,
    ChapterRead,
    ChapterResourcesPatchRequest,
    ChapterTransitionRequest,
    IncompleteProvisioningError,
    InvalidChapterGovernanceTransitionError,
    InvalidChapterTransitionError,
)
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.contracts.scheduler import DeferredEffectCreate
from app.contracts.scope import ScopeKind
from app.core.context import get_current_audit_context, use_audit_context
from app.repositories.archive_queries import ArchiveQueriesRepository, CountAndSamples
from app.repositories.archive_runs import ArchiveRunsRepository
from app.repositories.authority import AuthorityRepository
from app.repositories.chapter_templates import ChapterTemplatesRepository
from app.repositories.chapter_transitions import ChapterTransitionsRepository
from app.repositories.chapters import ChaptersRepository
from app.repositories.deferred_effects import enqueue_effect, list_archive_effects
from app.services.authority import current_time, evaluate, _row_to_read
from app.services.scheduler import DEFAULT_MAX_ATTEMPTS


PROVISIONING_TRANSITIONS = {
    ("proposed", "provisioning"),
    ("provisioning", "active"),
    ("provisioning", "provisioning_failed"),
    ("provisioning_failed", "provisioning"),
}
VALID_GOVERNANCE_TRANSITIONS = {
    ("active", "probation"),
    ("probation", "active"),
    ("active", "archiving"),
    ("probation", "archiving"),
}
VALID_ARCHIVE_WORKER_TRANSITIONS = {
    ("archiving", "archived"),
}
VALID_TRANSITIONS = (
    PROVISIONING_TRANSITIONS
    | VALID_GOVERNANCE_TRANSITIONS
    | VALID_ARCHIVE_WORKER_TRANSITIONS
)
GOVERNANCE_ACTION_TO_STATE = {
    "suspend": "probation",
    "restore": "active",
    "archive": "archiving",
}
ARCHIVE_PLAN_SAMPLE_LIMIT = 25
ARCHIVE_RUN_BATCH_LIMIT = 50
CHAPTER_GOVERNANCE_ACTION = "chapter.governance_transition"
CHAPTER_ARCHIVE_EXECUTE_ACTION = "chapter.archive_execute"
CHAPTER_ARCHIVE_FINALIZE_ACTION = "chapter.archive_finalize"
CHAPTER_STATE_CHANGED = "chapter.state_changed"
GOVERNANCE_TRANSITION_PAYLOAD_ALLOWLIST = {"to_state", "reason"}
ARCHIVE_EXECUTE_PAYLOAD_ALLOWLIST = {"archive_reason"}
ARCHIVE_EFFECT_APPLICATION_WITHDRAW = "chapter_archive_application_withdraw"
ARCHIVE_EFFECT_TICKET_CLOSE = "chapter_archive_ticket_close"
ARCHIVE_EFFECT_AUTHORITY_REVOKE = "chapter_archive_authority_revoke"
ARCHIVE_EFFECT_DEFERRED_EFFECT_CANCEL = "chapter_archive_deferred_effect_cancel"


def _make_request(
    *,
    expected_version: int,
    actor: ActorIdentity,
    request_surface: str,
    reason_text: str | None = None,
) -> MutationRequest:
    return MutationRequest(
        expected_version=expected_version,
        actor_kind=actor.actor_kind,
        actor_id=actor.actor_id,
        reason_text=reason_text,
        request_surface=request_surface,
    )


def _chapter_from_row(row: dict[str, Any]) -> ChapterRead:
    return ChapterRead(
        id=row["id"],
        name=row["name"],
        template_id=row["template_id"],
        template_snapshot=row["template_snapshot"],
        configuration=row["configuration"],
        state=row["state"],
        discord_resources=ChapterDiscordResources.model_validate(
            row["discord_resources"]
        ),
        created_at=row["created_at"],
        version=int(row["version"]),
    )


def _build_template_snapshot(template: dict[str, Any]) -> dict[str, Any]:
    if int(template["schema_version"]) != CURRENT_TEMPLATE_SCHEMA_VERSION:
        raise TemplateSchemaVersionMismatchError(int(template["schema_version"]))
    return {
        "template_id": str(template["id"]),
        "template_family_id": str(template["template_family_id"]),
        "template_version": int(template["version"]),
        "schema_version": int(template["schema_version"]),
        "channel_structure": deepcopy(template["channel_structure"]),
        "role_structure": deepcopy(template["role_structure"]),
        "default_permission_intents": deepcopy(template["default_permission_intents"]),
    }


def _verify_transition(*, chapter_id: str, from_state: str, to_state: str) -> None:
    if (from_state, to_state) not in PROVISIONING_TRANSITIONS:
        raise InvalidChapterTransitionError(
            chapter_id=chapter_id,
            from_state=from_state,
            to_state=to_state,
        )


def _expected_names(snapshot: dict[str, Any], key: str) -> set[str]:
    return {str(item["name"]) for item in snapshot.get(key, [])}


def _verify_provisioning_complete(chapter: dict[str, Any]) -> None:
    snapshot = chapter["template_snapshot"]
    resources = chapter["discord_resources"]

    if not resources.get("category_id"):
        raise IncompleteProvisioningError(missing="category")

    expected_role_names = _expected_names(snapshot, "role_structure")
    present_role_names = set(resources.get("role_ids", {}).keys())
    missing_roles = expected_role_names - present_role_names
    if missing_roles:
        raise IncompleteProvisioningError(missing=f"roles:{sorted(missing_roles)}")

    expected_channel_names = _expected_names(snapshot, "channel_structure")
    present_channel_names = set(resources.get("channel_ids", {}).keys())
    missing_channels = expected_channel_names - present_channel_names
    if missing_channels:
        raise IncompleteProvisioningError(
            missing=f"channels:{sorted(missing_channels)}"
        )


def _merge_resources(
    current: dict[str, Any],
    patch: ChapterDiscordResources,
) -> dict[str, Any]:
    merged = {
        "category_id": current.get("category_id"),
        "role_ids": dict(current.get("role_ids", {})),
        "channel_ids": dict(current.get("channel_ids", {})),
    }
    if patch.category_id is not None:
        merged["category_id"] = patch.category_id
    merged["role_ids"].update(patch.role_ids)
    merged["channel_ids"].update(patch.channel_ids)
    return merged


def _enqueue_failed_provisioning_effect(
    connection: Connection[Any],
    *,
    chapter_id: str,
    chapter_transition_id: Any,
    chapter: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    ctx = get_current_audit_context()
    if ctx is None:
        raise RuntimeError("missing audit context for deferred effect enqueue")
    effect = DeferredEffectCreate(
        subsystem="chapter_provisioning",
        effect_type="chapter_provisioning_retry",
        idempotency_key=(
            f"chapter_provision_retry:{chapter_id}:{chapter_transition_id}"
        ),
        payload_json={
            "chapter_id": chapter_id,
            "template_id": str(chapter["template_id"]),
            "partial_resources": chapter["discord_resources"],
            "failure_reason": reason,
            "failed_at_step": "api_confirm",
        },
        consequence_level="consequential",
        correlation_id=ctx.correlation_id,
        causation_id=ctx.causation_id,
    )
    return enqueue_effect(
        connection,
        effect=effect,
        correlation_id=ctx.correlation_id,
        max_attempts=DEFAULT_MAX_ATTEMPTS,
    )


class AuthorityDenied(Exception):
    def __init__(self, decision: AuthorityDecisionRead) -> None:
        self.decision = decision
        super().__init__("authority requirement denied")


def _section(counts: CountAndSamples) -> ChapterArchivePlanSectionRead:
    return ChapterArchivePlanSectionRead(
        count=counts.count,
        sample_ids=counts.sample_ids,
        has_more=counts.has_more,
    )


def _blocker(
    *,
    kind: str,
    item_id: str,
    reason: str,
    metadata: dict[str, Any] | None = None,
) -> ChapterArchiveBlockerRead:
    return ChapterArchiveBlockerRead(
        kind=kind,  # type: ignore[arg-type]
        item_id=item_id,
        reason=reason,
        metadata=metadata or {},
    )


def _blocker_dump(blocker: ChapterArchiveBlockerRead) -> dict[str, Any]:
    return blocker.model_dump(mode="json")


def _terminal_states(state_machine: dict[str, Any]) -> set[str]:
    return {
        str(state["key"])
        for state in state_machine.get("states", [])
        if state.get("terminal")
    }


def _edge_value(edge: dict[str, Any], key: str) -> Any:
    if key == "from":
        return edge.get("from", edge.get("from_state"))
    if key == "to":
        return edge.get("to", edge.get("to_state"))
    return edge.get(key)


def _find_close_edge(ticket_row: dict[str, Any]) -> dict[str, Any] | None:
    state_machine = ticket_row["category_snapshot"]["state_machine"]
    terminals = _terminal_states(state_machine)
    edges = [
        edge
        for edge in state_machine.get("edges", [])
        if str(_edge_value(edge, "from")) == str(ticket_row["state"])
        and str(_edge_value(edge, "to")) in terminals
        and str(edge.get("action")) in {"auto_close", "close"}
    ]
    return next(
        (edge for edge in edges if edge.get("action") == "auto_close"), None
    ) or (edges[0] if edges else None)


def _archive_context(correlation_id: Any, causation_id: Any) -> AuditContextRead:
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=causation_id,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=causation_id,
        ),
    )


def _enqueue_archive_effect(
    connection: Connection[Any],
    *,
    archive_run_id: Any,
    chapter_id: str,
    target_kind: str,
    target_id: str,
    expected_version: int,
    expected_state: str | None,
    archive_reason: str,
    effect_type: str,
    correlation_id: Any,
    causation_id: Any,
) -> dict[str, Any]:
    effect = DeferredEffectCreate(
        subsystem="chapter_archive",
        effect_type=effect_type,
        idempotency_key=(
            f"chapter_archive:{archive_run_id}:{target_kind}:{target_id}:v{expected_version}"
        ),
        payload_json={
            "archive_run_id": str(archive_run_id),
            "chapter_id": chapter_id,
            "target_kind": target_kind,
            "target_id": target_id,
            "expected_version": expected_version,
            "expected_state": expected_state,
            "archive_reason": archive_reason,
            "manual_review_policy": "block_archive",
        },
        consequence_level="consequential",
        correlation_id=correlation_id,
        causation_id=causation_id,
    )
    return enqueue_effect(
        connection,
        effect=effect,
        correlation_id=correlation_id,
        max_attempts=DEFAULT_MAX_ATTEMPTS,
    )


def _archive_run_to_status(
    *,
    chapter: dict[str, Any],
    run: dict[str, Any] | None,
    plan: ChapterArchivePlanRead | None,
) -> ChapterArchiveStatusRead:
    if run is None:
        return ChapterArchiveStatusRead(
            chapter_id=chapter["id"],
            chapter_state=chapter["state"],
            plan=plan,
        )
    return ChapterArchiveStatusRead(
        archive_run_id=run["id"],
        chapter_id=chapter["id"],
        chapter_state=chapter["state"],
        status=run["status"],
        correlation_id=run["correlation_id"],
        causation_id=run["causation_id"],
        archive_reason=run["archive_reason"],
        initiated_by_kind=run["initiated_by_kind"],
        initiated_by_id=run["initiated_by_id"],
        initiated_at=run["initiated_at"],
        completed_at=run["completed_at"],
        manual_review_items=[
            ChapterArchiveBlockerRead.model_validate(item)
            for item in run["manual_review_items"]
        ],
        plan=plan,
    )


def _merge_manual_items(
    existing: list[dict[str, Any]],
    additions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    keyed: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in [*existing, *additions]:
        keyed[
            (
                str(item.get("kind")),
                str(item.get("item_id")),
                str(item.get("reason")),
            )
        ] = item
    return list(keyed.values())


class ChaptersService:
    def __init__(
        self,
        chapters_repo: ChaptersRepository,
        chapter_transitions_repo: ChapterTransitionsRepository,
        archive_queries_repo: ArchiveQueriesRepository,
        archive_runs_repo: ArchiveRunsRepository,
        mutations_callable,
    ) -> None:
        self._chapters_repo = chapters_repo
        self._chapter_transitions_repo = chapter_transitions_repo
        self._archive_queries_repo = archive_queries_repo
        self._archive_runs_repo = archive_runs_repo
        self._chapter_templates_repo = ChapterTemplatesRepository(chapters_repo.db)
        self._mutations_callable = mutations_callable

    def _fetch_chapter_row_on(
        self,
        connection: Connection[Any],
        chapter_id: str,
    ) -> dict[str, Any]:
        row = self._chapters_repo._fetch_chapter_on(connection, chapter_id)
        if row is None:
            raise ChapterNotFoundError(chapter_id)
        return row

    def create_chapter(
        self,
        request: ChapterCreate,
        actor: ActorIdentity,
    ) -> tuple[ChapterRead, MutationResult]:
        chapter_id = str(uuid4())
        initial_resources = {"category_id": None, "role_ids": {}, "channel_ids": {}}

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            template = self._chapter_templates_repo._fetch_chapter_template_on(
                connection, request.template_id
            )
            if template is None:
                raise ChapterTemplateNotFoundError(request.template_id)
            snapshot = _build_template_snapshot(template)
            self._chapters_repo._insert_chapter_on(
                connection,
                row={
                    "id": chapter_id,
                    "name": request.name,
                    "template_id": request.template_id,
                    "template_snapshot": snapshot,
                    "configuration": request.configuration,
                    "state": "proposed",
                    "discord_resources": initial_resources,
                },
            )
            payload = {
                "chapter_id": chapter_id,
                "name": request.name,
                "template_id": str(request.template_id),
                "template_snapshot": snapshot,
                "configuration": request.configuration,
                "state": "proposed",
                "discord_resources": initial_resources,
                "originating_actor_kind": request.originating_actor_kind,
                "originating_actor_id": request.originating_actor_id,
            }
            if request.originating_actor_kind == "user":
                payload["originating_user_discord_id"] = request.originating_actor_id
            return StateChangeDraft(
                change_type="chapter.created",
                payload_json=payload,
            )

        try:
            result = self._mutations_callable(
                aggregate_type="chapter",
                aggregate_id=chapter_id,
                request=_make_request(
                    expected_version=0,
                    actor=actor,
                    request_surface="api:/api/v1/chapters",
                ),
                action_type="chapter.create",
                action_payload=request.model_dump(mode="json"),
                payload_allowlist=set(request.model_dump(mode="json").keys()),
                mutate_projection=mutate_projection,
            )
        except errors.UniqueViolation as error:
            raise ChapterDuplicateNameError(request.name) from error

        with self._chapters_repo.db.connection() as connection:
            read = _chapter_from_row(self._fetch_chapter_row_on(connection, chapter_id))
        return read, result

    def read_chapter(
        self,
        chapter_id: str,
    ) -> tuple[ChapterRead, str]:
        with self._chapters_repo.db.connection() as connection:
            read = _chapter_from_row(self._fetch_chapter_row_on(connection, chapter_id))
        return read, f'"{read.version}"'

    def patch_chapter_discord_resources(
        self,
        chapter_id: str,
        request: ChapterResourcesPatchRequest,
        actor: ActorIdentity,
        expected_version: int,
    ) -> tuple[ChapterRead, MutationResult]:
        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            row = self._chapters_repo._fetch_chapter_for_update_on(
                connection, chapter_id
            )
            if row is None:
                raise ChapterNotFoundError(chapter_id)
            merged = _merge_resources(row["discord_resources"], request.resources)
            self._chapters_repo._merge_chapter_discord_resources_on(
                connection,
                chapter_id=chapter_id,
                resources=merged,
            )
            return StateChangeDraft(
                change_type="chapter.discord_resources_patched",
                payload_json={
                    "chapter_id": chapter_id,
                    "discord_resources": merged,
                },
            )

        result = self._mutations_callable(
            aggregate_type="chapter",
            aggregate_id=chapter_id,
            request=_make_request(
                expected_version=expected_version,
                actor=actor,
                request_surface=f"api:/api/v1/chapters/{chapter_id}/discord-resources",
            ),
            action_type="chapter.discord_resources.patch",
            action_payload=request.model_dump(mode="json"),
            payload_allowlist=set(request.model_dump(mode="json").keys()),
            mutate_projection=mutate_projection,
        )
        with self._chapters_repo.db.connection() as connection:
            read = _chapter_from_row(self._fetch_chapter_row_on(connection, chapter_id))
        return read, result

    def transition_chapter(
        self,
        chapter_id: str,
        request: ChapterTransitionRequest,
        actor: ActorIdentity,
        expected_version: int,
    ) -> tuple[ChapterRead, MutationResult]:
        transition_id = uuid4()

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            row = self._chapters_repo._fetch_chapter_for_update_on(
                connection, chapter_id
            )
            if row is None:
                raise ChapterNotFoundError(chapter_id)
            from_state = row["state"]
            _verify_transition(
                chapter_id=chapter_id,
                from_state=from_state,
                to_state=request.to_state,
            )
            if request.to_state == "active":
                _verify_provisioning_complete(row)

            aggregate_seq = expected_version + 1
            self._chapter_transitions_repo._insert_chapter_transition_on(
                connection,
                row={
                    "id": transition_id,
                    "chapter_id": chapter_id,
                    "aggregate_seq": aggregate_seq,
                    "from_state": from_state,
                    "to_state": request.to_state,
                    "actor_kind": actor.actor_kind,
                    "actor_id": actor.actor_id,
                    "originating_actor_kind": request.originating_actor_kind,
                    "originating_actor_id": request.originating_actor_id,
                    "reason": request.reason,
                },
            )
            self._chapters_repo._update_chapter_state_on(
                connection,
                chapter_id=chapter_id,
                state=request.to_state,
            )
            payload: dict[str, Any] = {
                "chapter_transition_id": str(transition_id),
                "chapter_id": chapter_id,
                "from_state": from_state,
                "to_state": request.to_state,
                "reason": request.reason,
                "originating_actor_kind": request.originating_actor_kind,
                "originating_actor_id": request.originating_actor_id,
            }
            if request.originating_actor_kind == "user":
                payload["originating_user_discord_id"] = request.originating_actor_id
            if request.to_state == "provisioning_failed":
                updated = dict(row)
                updated["state"] = request.to_state
                effect_row = _enqueue_failed_provisioning_effect(
                    connection,
                    chapter_id=chapter_id,
                    chapter_transition_id=transition_id,
                    chapter=updated,
                    reason=request.reason,
                )
                payload["deferred_effect_id"] = str(effect_row["id"])
                payload["deferred_effect_idempotency_key"] = effect_row[
                    "idempotency_key"
                ]
            return StateChangeDraft(
                change_type="chapter.transitioned",
                payload_json=payload,
                diff_json={
                    "state": {"old": from_state, "new": request.to_state},
                },
            )

        result = self._mutations_callable(
            aggregate_type="chapter",
            aggregate_id=chapter_id,
            request=_make_request(
                expected_version=expected_version,
                actor=actor,
                request_surface=f"api:/api/v1/chapters/{chapter_id}/transitions",
                reason_text=request.reason,
            ),
            action_type="chapter.transition",
            action_payload=request.model_dump(mode="json"),
            payload_allowlist=set(request.model_dump(mode="json").keys()),
            mutate_projection=mutate_projection,
        )
        with self._chapters_repo.db.connection() as connection:
            read = _chapter_from_row(self._fetch_chapter_row_on(connection, chapter_id))
        return read, result

    def ensure_actor_has(
        self,
        *,
        permission: str,
        scope_kind: ScopeKind,
        scope_id: str | None,
        actor: ActorIdentity,
    ) -> None:
        authority_repo = AuthorityRepository(self._chapters_repo.db)
        grants = [
            _row_to_read(row)
            for row in authority_repo.list_grants(
                grantee_id=actor.actor_id,
                include_revoked=True,
                limit=None,
                after_id=None,
            )
        ]
        decision = evaluate(
            requirement=AuthorityRequirement(
                permission=permission,
                scope_kind=scope_kind,
                scope_id=scope_id,
            ),
            grants=grants,
            at=current_time(),
        )
        if not decision.allowed:
            raise AuthorityDenied(decision)

    def governance_transition(
        self,
        chapter_id: str,
        expected_version: int,
        request: ChapterGovernanceTransitionRequest,
        actor: ActorIdentity,
    ) -> tuple[ChapterRead, MutationResult]:
        expected_state = GOVERNANCE_ACTION_TO_STATE[request.action]
        if request.to_state != expected_state:
            raise InvalidChapterGovernanceTransitionError(
                chapter_id=chapter_id,
                action=request.action,
                from_state="unknown",
                to_state=request.to_state,
            )

        transition_id = uuid4()

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            row = self._chapters_repo._fetch_chapter_for_update_on(
                connection, chapter_id
            )
            if row is None:
                raise ChapterNotFoundError(chapter_id)
            from_state = row["state"]
            if (from_state, request.to_state) not in VALID_GOVERNANCE_TRANSITIONS:
                raise InvalidChapterGovernanceTransitionError(
                    chapter_id=chapter_id,
                    action=request.action,
                    from_state=from_state,
                    to_state=request.to_state,
                )
            self._chapter_transitions_repo._insert_chapter_transition_on(
                connection,
                row={
                    "id": transition_id,
                    "chapter_id": chapter_id,
                    "aggregate_seq": expected_version + 1,
                    "from_state": from_state,
                    "to_state": request.to_state,
                    "actor_kind": actor.actor_kind,
                    "actor_id": actor.actor_id,
                    "originating_actor_kind": request.originating_actor_kind,
                    "originating_actor_id": request.originating_actor_id,
                    "reason": request.reason,
                },
            )
            self._chapters_repo._update_chapter_state_on(
                connection, chapter_id=chapter_id, state=request.to_state
            )
            return StateChangeDraft(
                change_type=CHAPTER_STATE_CHANGED,
                payload_json={
                    "chapter_transition_id": str(transition_id),
                    "chapter_id": chapter_id,
                    "action": request.action,
                    "from_state": from_state,
                    "to_state": request.to_state,
                    "reason": request.reason,
                    "originating_actor_kind": request.originating_actor_kind,
                    "originating_actor_id": request.originating_actor_id,
                },
                diff_json={"state": {"old": from_state, "new": request.to_state}},
            )

        result = self._mutations_callable(
            aggregate_type="chapter",
            aggregate_id=chapter_id,
            request=_make_request(
                expected_version=expected_version,
                actor=actor,
                request_surface=f"api:/api/v1/chapters/{chapter_id}/governance-transitions",
                reason_text=request.reason,
            ),
            action_type=CHAPTER_GOVERNANCE_ACTION,
            action_payload=request.model_dump(mode="json"),
            payload_allowlist=GOVERNANCE_TRANSITION_PAYLOAD_ALLOWLIST,
            mutate_projection=mutate_projection,
            scope_kind="chapter",
            scope_id=chapter_id,
        )
        with self._chapters_repo.db.connection() as connection:
            read = _chapter_from_row(self._fetch_chapter_row_on(connection, chapter_id))
        return read, result

    def build_archive_plan(
        self,
        chapter_id: str,
        actor: ActorIdentity | None = None,
    ) -> ChapterArchivePlanRead:
        with self._chapters_repo.db.connection() as connection:
            row = self._fetch_chapter_row_on(connection, chapter_id)
            pending_applications = (
                self._archive_queries_repo._list_pending_applications_for_chapter_on(
                    connection,
                    chapter_id=chapter_id,
                    sample_limit=ARCHIVE_PLAN_SAMPLE_LIMIT,
                )
            )
            open_tickets = self._archive_queries_repo._list_open_tickets_for_chapter_on(
                connection,
                chapter_id=chapter_id,
                sample_limit=ARCHIVE_PLAN_SAMPLE_LIMIT,
            )
            active_grants = (
                self._archive_queries_repo._list_active_authority_grants_for_chapter_on(
                    connection,
                    chapter_id=chapter_id,
                    sample_limit=ARCHIVE_PLAN_SAMPLE_LIMIT,
                )
            )
            unresolved_effects = self._archive_queries_repo._list_unresolved_deferred_effects_for_chapter_on(
                connection,
                chapter_id=chapter_id,
                sample_limit=ARCHIVE_PLAN_SAMPLE_LIMIT,
            )
            active_roster = (
                self._archive_queries_repo._list_active_roster_entries_for_chapter_on(
                    connection,
                    chapter_id=chapter_id,
                    sample_limit=ARCHIVE_PLAN_SAMPLE_LIMIT,
                )
            )
            roles = self._archive_queries_repo._list_chapter_roles_for_plan_on(
                connection,
                chapter_id=chapter_id,
                sample_limit=ARCHIVE_PLAN_SAMPLE_LIMIT,
            )
            ticket_rows = self._archive_queries_repo._iter_open_tickets_for_archive_on(
                connection, chapter_id=chapter_id
            )

        blockers: list[ChapterArchiveBlockerRead] = []
        blockers.extend(
            _blocker(kind="application", item_id=item_id, reason="pending_application")
            for item_id in pending_applications.sample_ids
        )
        blockers.extend(
            _blocker(
                kind="authority_grant", item_id=item_id, reason="active_authority_grant"
            )
            for item_id in active_grants.sample_ids
        )
        blockers.extend(
            _blocker(
                kind="deferred_effect",
                item_id=item_id,
                reason="unresolved_deferred_effect",
            )
            for item_id in unresolved_effects.sample_ids
        )
        for ticket in ticket_rows[:ARCHIVE_PLAN_SAMPLE_LIMIT]:
            close_edge = _find_close_edge(ticket)
            reason = (
                "open_ticket"
                if close_edge is not None
                else "ticket_requires_manual_review"
            )
            blockers.append(
                _blocker(
                    kind="ticket",
                    item_id=str(ticket["id"]),
                    reason=reason,
                    metadata={
                        "state": ticket["state"],
                        "closable": close_edge is not None,
                    },
                )
            )

        return ChapterArchivePlanRead(
            chapter_id=chapter_id,
            chapter_state=row["state"],
            generated_at=datetime.now(UTC),
            pending_applications=_section(pending_applications),
            open_tickets=_section(open_tickets),
            active_authority_grants=_section(active_grants),
            unresolved_deferred_effects=_section(unresolved_effects),
            active_roster_entries=_section(active_roster),
            chapter_roles=_section(roles),
            discord_resources=ChapterDiscordResources.model_validate(
                row["discord_resources"]
            ),
            blockers=blockers,
        )

    def _prepare_archive_effects_on(
        self,
        connection: Connection[Any],
        *,
        archive_run_id: Any,
        chapter_id: str,
        archive_reason: str,
        correlation_id: Any,
        causation_id: Any,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        effect_ids: list[str] = []
        manual_items: list[dict[str, Any]] = []

        for (
            application
        ) in self._archive_queries_repo._iter_pending_applications_for_archive_on(
            connection, chapter_id=chapter_id
        ):
            row = _enqueue_archive_effect(
                connection,
                archive_run_id=archive_run_id,
                chapter_id=chapter_id,
                target_kind="application",
                target_id=str(application["id"]),
                expected_version=int(application["version"]),
                expected_state=str(application["state"]),
                archive_reason=archive_reason,
                effect_type=ARCHIVE_EFFECT_APPLICATION_WITHDRAW,
                correlation_id=correlation_id,
                causation_id=causation_id,
            )
            effect_ids.append(str(row["id"]))

        for ticket in self._archive_queries_repo._iter_open_tickets_for_archive_on(
            connection, chapter_id=chapter_id
        ):
            close_edge = _find_close_edge(ticket)
            if close_edge is None:
                manual_items.append(
                    _blocker_dump(
                        _blocker(
                            kind="ticket",
                            item_id=str(ticket["id"]),
                            reason="ticket_requires_manual_review",
                            metadata={"state": ticket["state"]},
                        )
                    )
                )
                continue
            row = _enqueue_archive_effect(
                connection,
                archive_run_id=archive_run_id,
                chapter_id=chapter_id,
                target_kind="ticket",
                target_id=str(ticket["id"]),
                expected_version=int(ticket["version"]),
                expected_state=str(ticket["state"]),
                archive_reason=archive_reason,
                effect_type=ARCHIVE_EFFECT_TICKET_CLOSE,
                correlation_id=correlation_id,
                causation_id=causation_id,
            )
            effect_ids.append(str(row["id"]))

        for grant in self._archive_queries_repo._iter_active_grants_for_archive_on(
            connection, chapter_id=chapter_id
        ):
            row = _enqueue_archive_effect(
                connection,
                archive_run_id=archive_run_id,
                chapter_id=chapter_id,
                target_kind="authority_grant",
                target_id=str(grant["id"]),
                expected_version=int(grant["version"]),
                expected_state="active",
                archive_reason=archive_reason,
                effect_type=ARCHIVE_EFFECT_AUTHORITY_REVOKE,
                correlation_id=correlation_id,
                causation_id=causation_id,
            )
            effect_ids.append(str(row["id"]))

        for (
            effect
        ) in self._archive_queries_repo._iter_unresolved_chapter_effects_for_archive_on(
            connection,
            chapter_id=chapter_id,
            exclude_archive_run_id=str(archive_run_id),
        ):
            row = _enqueue_archive_effect(
                connection,
                archive_run_id=archive_run_id,
                chapter_id=chapter_id,
                target_kind="deferred_effect",
                target_id=str(effect["id"]),
                expected_version=0,
                expected_state=str(effect["status"]),
                archive_reason=archive_reason,
                effect_type=ARCHIVE_EFFECT_DEFERRED_EFFECT_CANCEL,
                correlation_id=correlation_id,
                causation_id=causation_id,
            )
            effect_ids.append(str(row["id"]))

        return effect_ids, manual_items

    def execute_archive(
        self,
        chapter_id: str,
        expected_version: int,
        request: ChapterArchiveExecuteRequest,
        actor: ActorIdentity,
    ) -> tuple[ChapterArchiveStatusRead, MutationResult]:
        archive_run_id = uuid4()
        transition_id = uuid4()
        current_ctx = get_current_audit_context()
        if current_ctx is None:
            raise RuntimeError("missing audit context for archive execute")
        run_correlation_id = current_ctx.correlation_id
        run_causation_id = current_ctx.causation_id or uuid4()
        archive_ctx = _archive_context(run_correlation_id, run_causation_id)
        queued_effect_ids: list[str] = []
        manual_items: list[dict[str, Any]] = []

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            nonlocal queued_effect_ids, manual_items
            row = self._chapters_repo._fetch_chapter_for_update_on(
                connection, chapter_id
            )
            if row is None:
                raise ChapterNotFoundError(chapter_id)
            in_progress = self._archive_runs_repo._fetch_in_progress_archive_run_on(
                connection, chapter_id=chapter_id
            )
            if in_progress is not None:
                raise ChapterArchiveInProgressError(
                    archive_run_id=in_progress["id"],
                    correlation_id=in_progress["correlation_id"],
                )
            from_state = row["state"]
            if from_state not in {"active", "probation"}:
                raise ChapterArchivePrerequisitesError(
                    chapter_id=chapter_id, state=from_state
                )

            self._archive_runs_repo._insert_archive_run_on(
                connection,
                row={
                    "id": archive_run_id,
                    "chapter_id": chapter_id,
                    "correlation_id": run_correlation_id,
                    "causation_id": run_causation_id,
                    "archive_reason": request.archive_reason,
                    "initiated_by_kind": actor.actor_kind,
                    "initiated_by_id": actor.actor_id,
                    "manual_review_items": [],
                },
            )
            self._chapter_transitions_repo._insert_chapter_transition_on(
                connection,
                row={
                    "id": transition_id,
                    "chapter_id": chapter_id,
                    "aggregate_seq": expected_version + 1,
                    "from_state": from_state,
                    "to_state": "archiving",
                    "actor_kind": actor.actor_kind,
                    "actor_id": actor.actor_id,
                    "originating_actor_kind": "user",
                    "originating_actor_id": actor.actor_id,
                    "reason": request.archive_reason,
                },
            )
            self._chapters_repo._update_chapter_state_on(
                connection, chapter_id=chapter_id, state="archiving"
            )
            queued_effect_ids, manual_items = self._prepare_archive_effects_on(
                connection,
                archive_run_id=archive_run_id,
                chapter_id=chapter_id,
                archive_reason=request.archive_reason,
                correlation_id=run_correlation_id,
                causation_id=run_causation_id,
            )
            if manual_items:
                self._archive_runs_repo._update_archive_run_manual_review_items_on(
                    connection,
                    archive_run_id=archive_run_id,
                    items=manual_items,
                )
            return StateChangeDraft(
                change_type=CHAPTER_STATE_CHANGED,
                payload_json={
                    "archive_run_id": str(archive_run_id),
                    "chapter_transition_id": str(transition_id),
                    "chapter_id": chapter_id,
                    "from_state": from_state,
                    "to_state": "archiving",
                    "correlation_id": str(run_correlation_id),
                    "causation_id": str(run_causation_id),
                    "queued_effect_ids": queued_effect_ids,
                    "manual_review_items": manual_items,
                },
                diff_json={"state": {"old": from_state, "new": "archiving"}},
            )

        with use_audit_context(archive_ctx):
            result = self._mutations_callable(
                aggregate_type="chapter",
                aggregate_id=chapter_id,
                request=_make_request(
                    expected_version=expected_version,
                    actor=actor,
                    request_surface=f"api:/api/v1/chapters/{chapter_id}/archive-execute",
                    reason_text=request.archive_reason,
                ).model_copy(
                    update={
                        "correlation_id": run_correlation_id,
                        "causation_id": run_causation_id,
                    }
                ),
                action_type=CHAPTER_ARCHIVE_EXECUTE_ACTION,
                action_payload=request.model_dump(mode="json"),
                payload_allowlist=ARCHIVE_EXECUTE_PAYLOAD_ALLOWLIST,
                mutate_projection=mutate_projection,
                scope_kind="chapter",
                scope_id=chapter_id,
            )
        return self.archive_status(chapter_id, actor), result

    def archive_status(
        self,
        chapter_id: str,
        actor: ActorIdentity | None = None,
    ) -> ChapterArchiveStatusRead:
        with self._chapters_repo.db.connection() as connection:
            chapter = self._fetch_chapter_row_on(connection, chapter_id)
            run = self._archive_runs_repo._fetch_in_progress_archive_run_on(
                connection, chapter_id=chapter_id
            )
            if run is None:
                run = self._archive_runs_repo._fetch_latest_archive_run_on(
                    connection, chapter_id=chapter_id
                )
        plan = self.build_archive_plan(chapter_id, actor) if run is not None else None
        return _archive_run_to_status(chapter=chapter, run=run, plan=plan)

    def list_active_archive_runs(self) -> list[dict[str, Any]]:
        with self._chapters_repo.db.connection() as connection:
            return self._archive_runs_repo._list_in_progress_archive_runs_on(
                connection,
                limit=ARCHIVE_RUN_BATCH_LIMIT,
            )

    def record_archive_manual_review_items(
        self,
        *,
        archive_run_id: Any,
        items: list[dict[str, Any]],
    ) -> None:
        if not items:
            return
        with self._archive_runs_repo.db.transaction() as connection:
            run = self._archive_runs_repo._fetch_archive_run_for_update_on(
                connection, archive_run_id=archive_run_id
            )
            if run is None or run["status"] != "in_progress":
                return
            self._archive_runs_repo._update_archive_run_manual_review_items_on(
                connection,
                archive_run_id=archive_run_id,
                items=_merge_manual_items(run["manual_review_items"], items),
            )

    def enqueue_missing_archive_effects(
        self,
        *,
        archive_run: dict[str, Any],
    ) -> None:
        with self._archive_runs_repo.db.transaction() as connection:
            run = self._archive_runs_repo._fetch_archive_run_for_update_on(
                connection, archive_run_id=archive_run["id"]
            )
            if run is None or run["status"] != "in_progress":
                return
            queued_effect_ids, manual_items = self._prepare_archive_effects_on(
                connection,
                archive_run_id=run["id"],
                chapter_id=run["chapter_id"],
                archive_reason=run["archive_reason"],
                correlation_id=run["correlation_id"],
                causation_id=run["causation_id"],
            )
            if manual_items:
                self._archive_runs_repo._update_archive_run_manual_review_items_on(
                    connection,
                    archive_run_id=run["id"],
                    items=_merge_manual_items(run["manual_review_items"], manual_items),
                )

    def finalize_archive_run(
        self,
        *,
        archive_run: dict[str, Any],
        actor: ActorIdentity,
    ) -> ChapterArchiveStatusRead | None:
        with self._chapters_repo.db.connection() as connection:
            fresh_run = self._archive_runs_repo._fetch_latest_archive_run_on(
                connection,
                chapter_id=archive_run["chapter_id"],
            )
            if fresh_run is None or fresh_run["status"] != "in_progress":
                return None
            archive_effects = list_archive_effects(
                connection,
                archive_run_id=fresh_run["id"],
                statuses={"queued", "claimed", "failed"},
            )
        plan = self.build_archive_plan(archive_run["chapter_id"], actor)
        has_pending_plan_items = any(
            section.count > 0
            for section in (
                plan.pending_applications,
                plan.open_tickets,
                plan.active_authority_grants,
                plan.unresolved_deferred_effects,
            )
        )
        if (
            archive_effects
            or has_pending_plan_items
            or fresh_run["manual_review_items"]
        ):
            return None

        transition_id = uuid4()

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            run = self._archive_runs_repo._fetch_archive_run_for_update_on(
                connection, archive_run_id=fresh_run["id"]
            )
            if run is None or run["status"] != "in_progress":
                raise ChapterArchivePrerequisitesError(
                    chapter_id=fresh_run["chapter_id"],
                    state="archive_run_not_in_progress",
                )
            chapter = self._chapters_repo._fetch_chapter_for_update_on(
                connection,
                fresh_run["chapter_id"],
            )
            if chapter is None:
                raise ChapterNotFoundError(fresh_run["chapter_id"])
            from_state = chapter["state"]
            if (from_state, "archived") not in VALID_ARCHIVE_WORKER_TRANSITIONS:
                raise ChapterArchivePrerequisitesError(
                    chapter_id=fresh_run["chapter_id"],
                    state=from_state,
                )
            self._chapter_transitions_repo._insert_chapter_transition_on(
                connection,
                row={
                    "id": transition_id,
                    "chapter_id": fresh_run["chapter_id"],
                    "aggregate_seq": int(chapter["version"]) + 1,
                    "from_state": from_state,
                    "to_state": "archived",
                    "actor_kind": actor.actor_kind,
                    "actor_id": actor.actor_id,
                    "originating_actor_kind": "service",
                    "originating_actor_id": actor.actor_id,
                    "reason": fresh_run["archive_reason"],
                },
            )
            self._chapters_repo._update_chapter_state_on(
                connection,
                chapter_id=fresh_run["chapter_id"],
                state="archived",
            )
            self._archive_runs_repo._mark_archive_run_completed_on(
                connection, archive_run_id=fresh_run["id"]
            )
            return StateChangeDraft(
                change_type=CHAPTER_STATE_CHANGED,
                payload_json={
                    "archive_run_id": str(fresh_run["id"]),
                    "chapter_transition_id": str(transition_id),
                    "chapter_id": fresh_run["chapter_id"],
                    "from_state": from_state,
                    "to_state": "archived",
                    "completed_at": datetime.now(UTC).isoformat(),
                },
                diff_json={"state": {"old": from_state, "new": "archived"}},
            )

        ctx = _archive_context(fresh_run["correlation_id"], fresh_run["causation_id"])
        expected_version = self._fetch_chapter_row_for_version(fresh_run["chapter_id"])
        with use_audit_context(ctx):
            self._mutations_callable(
                aggregate_type="chapter",
                aggregate_id=fresh_run["chapter_id"],
                request=_make_request(
                    expected_version=expected_version,
                    actor=actor,
                    request_surface="worker:chapter_archive.finalize",
                    reason_text=fresh_run["archive_reason"],
                ).model_copy(
                    update={
                        "correlation_id": fresh_run["correlation_id"],
                        "causation_id": fresh_run["causation_id"],
                    }
                ),
                action_type=CHAPTER_ARCHIVE_FINALIZE_ACTION,
                action_payload={"archive_reason": fresh_run["archive_reason"]},
                payload_allowlist=ARCHIVE_EXECUTE_PAYLOAD_ALLOWLIST,
                mutate_projection=mutate_projection,
                scope_kind="chapter",
                scope_id=fresh_run["chapter_id"],
            )
        return self.archive_status(fresh_run["chapter_id"], actor)

    def _fetch_chapter_row_for_version(self, chapter_id: str) -> int:
        with self._chapters_repo.db.connection() as connection:
            row = self._fetch_chapter_row_on(connection, chapter_id)
        return int(row["version"])

    def _archive_execute_on(
        self,
        connection: Connection[Any],
        *,
        chapter_id: str,
        expected_version: int,
        request: ChapterArchiveExecuteRequest,
        actor: ActorIdentity,
        archive_run_id: Any,
        transition_id: Any,
        run_correlation_id: Any,
        run_causation_id: Any,
    ) -> StateChangeDraft:
        row = self._chapters_repo._fetch_chapter_for_update_on(connection, chapter_id)
        if row is None:
            raise ChapterNotFoundError(chapter_id)
        in_progress = self._archive_runs_repo._fetch_in_progress_archive_run_on(
            connection, chapter_id=chapter_id
        )
        if in_progress is not None:
            raise ChapterArchiveInProgressError(
                archive_run_id=in_progress["id"],
                correlation_id=in_progress["correlation_id"],
            )
        from_state = row["state"]
        if from_state not in {"active", "probation"}:
            raise ChapterArchivePrerequisitesError(
                chapter_id=chapter_id, state=from_state
            )

        self._archive_runs_repo._insert_archive_run_on(
            connection,
            row={
                "id": archive_run_id,
                "chapter_id": chapter_id,
                "correlation_id": run_correlation_id,
                "causation_id": run_causation_id,
                "archive_reason": request.archive_reason,
                "initiated_by_kind": actor.actor_kind,
                "initiated_by_id": actor.actor_id,
                "manual_review_items": [],
            },
        )
        self._chapter_transitions_repo._insert_chapter_transition_on(
            connection,
            row={
                "id": transition_id,
                "chapter_id": chapter_id,
                "aggregate_seq": expected_version + 1,
                "from_state": from_state,
                "to_state": "archiving",
                "actor_kind": actor.actor_kind,
                "actor_id": actor.actor_id,
                "originating_actor_kind": "user",
                "originating_actor_id": actor.actor_id,
                "reason": request.archive_reason,
            },
        )
        self._chapters_repo._update_chapter_state_on(
            connection, chapter_id=chapter_id, state="archiving"
        )
        queued_effect_ids, manual_items = self._prepare_archive_effects_on(
            connection,
            archive_run_id=archive_run_id,
            chapter_id=chapter_id,
            archive_reason=request.archive_reason,
            correlation_id=run_correlation_id,
            causation_id=run_causation_id,
        )
        if manual_items:
            self._archive_runs_repo._update_archive_run_manual_review_items_on(
                connection,
                archive_run_id=archive_run_id,
                items=manual_items,
            )
        return StateChangeDraft(
            change_type=CHAPTER_STATE_CHANGED,
            payload_json={
                "archive_run_id": str(archive_run_id),
                "chapter_transition_id": str(transition_id),
                "chapter_id": chapter_id,
                "from_state": from_state,
                "to_state": "archiving",
                "correlation_id": str(run_correlation_id),
                "causation_id": str(run_causation_id),
                "queued_effect_ids": queued_effect_ids,
                "manual_review_items": manual_items,
            },
            diff_json={"state": {"old": from_state, "new": "archiving"}},
        )

    def _finalize_archive_run_on(
        self,
        connection: Connection[Any],
        *,
        fresh_run: dict[str, Any],
        transition_id: Any,
        actor: ActorIdentity,
    ) -> StateChangeDraft:
        run = self._archive_runs_repo._fetch_archive_run_for_update_on(
            connection, archive_run_id=fresh_run["id"]
        )
        if run is None or run["status"] != "in_progress":
            raise ChapterArchivePrerequisitesError(
                chapter_id=fresh_run["chapter_id"],
                state="archive_run_not_in_progress",
            )
        chapter = self._chapters_repo._fetch_chapter_for_update_on(
            connection,
            fresh_run["chapter_id"],
        )
        if chapter is None:
            raise ChapterNotFoundError(fresh_run["chapter_id"])
        from_state = chapter["state"]
        if (from_state, "archived") not in VALID_ARCHIVE_WORKER_TRANSITIONS:
            raise ChapterArchivePrerequisitesError(
                chapter_id=fresh_run["chapter_id"],
                state=from_state,
            )
        self._chapter_transitions_repo._insert_chapter_transition_on(
            connection,
            row={
                "id": transition_id,
                "chapter_id": fresh_run["chapter_id"],
                "aggregate_seq": int(chapter["version"]) + 1,
                "from_state": from_state,
                "to_state": "archived",
                "actor_kind": actor.actor_kind,
                "actor_id": actor.actor_id,
                "originating_actor_kind": "service",
                "originating_actor_id": actor.actor_id,
                "reason": fresh_run["archive_reason"],
            },
        )
        self._chapters_repo._update_chapter_state_on(
            connection,
            chapter_id=fresh_run["chapter_id"],
            state="archived",
        )
        self._archive_runs_repo._mark_archive_run_completed_on(
            connection, archive_run_id=fresh_run["id"]
        )
        return StateChangeDraft(
            change_type=CHAPTER_STATE_CHANGED,
            payload_json={
                "archive_run_id": str(fresh_run["id"]),
                "chapter_transition_id": str(transition_id),
                "chapter_id": fresh_run["chapter_id"],
                "from_state": from_state,
                "to_state": "archived",
                "completed_at": datetime.now(UTC).isoformat(),
            },
            diff_json={"state": {"old": from_state, "new": "archived"}},
        )


__all__ = [
    "ARCHIVE_EFFECT_APPLICATION_WITHDRAW",
    "ARCHIVE_EFFECT_AUTHORITY_REVOKE",
    "ARCHIVE_EFFECT_DEFERRED_EFFECT_CANCEL",
    "ARCHIVE_EFFECT_TICKET_CLOSE",
    "AuthorityDenied",
    "ChaptersService",
]
