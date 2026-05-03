from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import Any
from uuid import UUID

from app.contracts.actor import ActorIdentity
from app.contracts.applications import ApplicationTransitionRequest
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.mutations import StaleMutationError
from app.contracts.scheduler import DeferredEffectRead
from app.contracts.tickets import TicketTransitionRequest
from app.core.context import use_audit_context
from app.core.settings import Settings
from app.repositories.application_messages import ApplicationMessagesRepository
from app.repositories.applications import ApplicationsRepository
from app.repositories.archive_queries import ArchiveQueriesRepository
from app.repositories.archive_runs import ArchiveRunsRepository
from app.repositories.authority import AuthorityRepository
from app.repositories.chapter_roles import ChapterRolesRepository
from app.repositories.chapter_transitions import ChapterTransitionsRepository
from app.repositories.chapters import ChaptersRepository
from app.repositories.db import PostgresDatabase
from app.repositories.deferred_effects import DeferredEffectsRepository
from app.repositories.ticket_categories import TicketCategoriesRepository
from app.repositories.ticket_messages import TicketMessagesRepository
from app.repositories.tickets import TicketsRepository
from app.repositories.forms import FormsRepository
from app.repositories.members import MembersRepository
from app.repositories.public_chapters import PublicChaptersRepository
from app.repositories.roster import RosterRepository
from app.services.applications import ApplicationsService
from app.services.authority import AuthorityService, current_time
from app.services.chapters import (
    ARCHIVE_EFFECT_APPLICATION_WITHDRAW,
    ARCHIVE_EFFECT_AUTHORITY_REVOKE,
    ARCHIVE_EFFECT_DEFERRED_EFFECT_CANCEL,
    ARCHIVE_EFFECT_TICKET_CLOSE,
    AuthorityDenied,
    ChaptersService,
)
from app.services.scheduler import register_scheduler_handler
from app.services.file_upload import FileUploadService, build_s3_client
from app.services.mutations import mutate_entity
from app.services.ticket_messages import TicketMessagesService
from app.services.tickets import TicketsService


CHAPTER_ARCHIVER_ID = "chapter-archiver"
ARCHIVE_WORKER_ACTOR = ActorIdentity(
    actor_kind="service",
    actor_id=CHAPTER_ARCHIVER_ID,
)
ARCHIVE_TICK_INTERVAL_SECONDS = 60
_PENDING_APPLICATION_STATES = {"submitted", "queued", "claimed", "in_review"}

def _build_tickets_service(db: PostgresDatabase) -> TicketsService:
    tickets_repo = TicketsRepository(db)
    ticket_messages_repo = TicketMessagesRepository(db)
    ticket_messages_service = TicketMessagesService(
        tickets_repo=tickets_repo,
        ticket_messages_repo=ticket_messages_repo,
    )
    return TicketsService(
        tickets_repo=tickets_repo,
        ticket_categories_repo=TicketCategoriesRepository(db),
        ticket_messages_repo=ticket_messages_repo,
        ticket_messages_service=ticket_messages_service,
        mutations_callable=partial(mutate_entity, db=db),
    )


def _build_applications_service(
    db: PostgresDatabase,
) -> tuple[ApplicationsRepository, ApplicationsService]:
    settings = Settings()
    applications_repo = ApplicationsRepository(db)
    return applications_repo, ApplicationsService(
        applications_repo=applications_repo,
        application_messages_repo=ApplicationMessagesRepository(db),
        forms_repo=FormsRepository(db),
        public_chapters_repo=PublicChaptersRepository(db),
        members_repo=MembersRepository(db),
        file_upload_service=FileUploadService(
            s3_client=build_s3_client(settings),
            settings=settings,
        ),
        mutations_callable=partial(mutate_entity, db=db),
        notification_emitter=None,  # archive does not trigger public submit
    )


def _build_chapters_service(db: PostgresDatabase) -> ChaptersService:
    return ChaptersService(
        chapters_repo=ChaptersRepository(db=db),
        chapter_transitions_repo=ChapterTransitionsRepository(db=db),
        archive_queries_repo=ArchiveQueriesRepository(db=db),
        archive_runs_repo=ArchiveRunsRepository(db=db),
        deferred_effects_repo=DeferredEffectsRepository(db=db),
        mutations_callable=partial(mutate_entity, db=db),
    )


def _audit_context(row: dict[str, Any]) -> AuditContextRead:
    return AuditContextRead(
        correlation_id=row["correlation_id"],
        causation_id=row["causation_id"],
        headers=CorrelationHeadersRead(
            x_correlation_id=row["correlation_id"],
            x_causation_id=row["causation_id"],
        ),
    )


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


def _manual_item(
    *,
    kind: str,
    item_id: str,
    reason: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "item_id": item_id,
        "reason": reason,
        "metadata": metadata or {},
    }


def _mark_valid(
    deferred_effects_repo: DeferredEffectsRepository,
    connection,
    effect_id: UUID,
) -> None:
    try:
        deferred_effects_repo._update_precondition_state_on(
            connection,
            effect_id=effect_id,
            new_state="valid",
        )
    except Exception:
        return


def _skip_effect(
    deferred_effects_repo: DeferredEffectsRepository,
    connection,
    effect_id: UUID,
    reason: str,
) -> None:
    deferred_effects_repo._mark_unclaimed_deferred_effect_skipped_on(
        connection,
        effect_id=effect_id,
        reason=reason,
    )


def _validate_archive_effects(
    db: PostgresDatabase, archive_run: dict[str, Any]
) -> None:
    applications_repo, _applications_service = _build_applications_service(db)
    chapters_service = _build_chapters_service(db)
    tickets_repo = TicketsRepository(db)
    deferred_effects_repo = DeferredEffectsRepository(db)
    with db.transaction() as connection:
        effects = deferred_effects_repo._list_archive_effects_on(
            connection,
            archive_run_id=archive_run["id"],
            statuses={"queued", "failed"},
        )
        manual_items: list[dict[str, Any]] = []
        for effect in effects:
            payload = effect["payload_json"]
            target_kind = payload["target_kind"]
            target_id = payload["target_id"]
            expected_version = int(payload.get("expected_version") or 0)
            expected_state = payload.get("expected_state")

            if target_kind == "application":
                application = applications_repo._get_application_on(
                    connection,
                    application_id=UUID(target_id),
                )
                if (
                    application is None
                    or application["state"] not in _PENDING_APPLICATION_STATES
                ):
                    _skip_effect(
                        deferred_effects_repo,
                        connection,
                        effect["id"],
                        "already_resolved",
                    )
                elif (
                    int(application["version"]) == expected_version
                    and application["state"] == expected_state
                ):
                    _mark_valid(deferred_effects_repo, connection, effect["id"])
                else:
                    _skip_effect(
                        deferred_effects_repo,
                        connection,
                        effect["id"],
                        "stale_precondition",
                    )
            elif target_kind == "ticket":
                ticket = tickets_repo._get_ticket_on(connection, UUID(target_id))
                if ticket is None or ticket["terminal_at"] is not None:
                    _skip_effect(
                        deferred_effects_repo,
                        connection,
                        effect["id"],
                        "already_resolved",
                    )
                    continue
                if _find_close_edge(ticket) is None:
                    manual_items.append(
                        _manual_item(
                            kind="ticket",
                            item_id=target_id,
                            reason="ticket_requires_manual_review",
                            metadata={"state": ticket["state"]},
                        )
                    )
                    _skip_effect(
                        deferred_effects_repo,
                        connection,
                        effect["id"],
                        "manual_review_required",
                    )
                elif (
                    int(ticket["version"]) == expected_version
                    and ticket["state"] == expected_state
                ):
                    _mark_valid(deferred_effects_repo, connection, effect["id"])
                else:
                    _skip_effect(
                        deferred_effects_repo,
                        connection,
                        effect["id"],
                        "stale_precondition",
                    )
            elif target_kind == "authority_grant":
                grant = AuthorityRepository(db)._fetch_grant_on(
                    connection,
                    grant_id=UUID(target_id),
                )
                if (
                    grant is None
                    or grant["revoked_at"] is not None
                    or (
                        grant["expires_at"] is not None
                        and grant["expires_at"] <= current_time()
                    )
                ):
                    _skip_effect(
                        deferred_effects_repo,
                        connection,
                        effect["id"],
                        "already_resolved",
                    )
                elif int(grant["current_seq"]) == expected_version:
                    _mark_valid(deferred_effects_repo, connection, effect["id"])
                else:
                    _skip_effect(
                        deferred_effects_repo,
                        connection,
                        effect["id"],
                        "stale_precondition",
                    )
            elif target_kind == "deferred_effect":
                target = deferred_effects_repo._fetch_deferred_effect_on(
                    connection, UUID(target_id)
                )
                if target is None or target["status"] in {"completed", "skipped"}:
                    _skip_effect(
                        deferred_effects_repo,
                        connection,
                        effect["id"],
                        "already_resolved",
                    )
                elif target["status"] in {"queued", "failed"} or (
                    target["status"] == "claimed"
                    and target["lease_until"] is not None
                    and target["lease_until"] < datetime.now(UTC)
                ):
                    _mark_valid(deferred_effects_repo, connection, effect["id"])
                else:
                    manual_items.append(
                        _manual_item(
                            kind="deferred_effect",
                            item_id=target_id,
                            reason="deferred_effect_in_flight",
                        )
                    )
                    _skip_effect(
                        deferred_effects_repo,
                        connection,
                        effect["id"],
                        "manual_review_required",
                    )
        if manual_items:
            chapters_service.record_archive_manual_review_items(
                archive_run_id=archive_run["id"],
                items=manual_items,
            )


def archive_worker_tick(db: PostgresDatabase) -> list[Any]:
    chapters_service = _build_chapters_service(db)
    statuses = []
    for archive_run in chapters_service.list_active_archive_runs():
        try:
            with use_audit_context(_audit_context(archive_run)):
                chapters_service.enqueue_missing_archive_effects(
                    archive_run=archive_run
                )
                _validate_archive_effects(db, archive_run)
                chapters_service.enqueue_missing_archive_effects(
                    archive_run=archive_run
                )
                finalized = chapters_service.finalize_archive_run(
                    archive_run=archive_run,
                    actor=ARCHIVE_WORKER_ACTOR,
                )
                statuses.append(
                    finalized
                    if finalized is not None
                    else chapters_service.archive_status(
                        archive_run["chapter_id"],
                        ARCHIVE_WORKER_ACTOR,
                    )
                )
        except StaleMutationError:
            continue
    return statuses


def _record_authority_denied(
    effect: DeferredEffectRead,
    permission: str,
    *,
    db: PostgresDatabase,
) -> None:
    chapters_service = _build_chapters_service(db)
    chapters_service.record_archive_manual_review_items(
        archive_run_id=UUID(str(effect.payload_json["archive_run_id"])),
        items=[
            _manual_item(
                kind=str(effect.payload_json["target_kind"]),
                item_id=str(effect.payload_json["target_id"]),
                reason="archive_worker_authority_denied",
                metadata={"permission": permission},
            )
        ],
    )


@register_scheduler_handler(ARCHIVE_EFFECT_APPLICATION_WITHDRAW)
def handle_archive_application_withdraw(
    effect: DeferredEffectRead,
    *,
    db: PostgresDatabase,
) -> None:
    applications_repo, applications_service = _build_applications_service(db)
    chapters_service = _build_chapters_service(db)
    payload = effect.payload_json
    permission = "application.withdraw"
    try:
        chapters_service.ensure_actor_has(
            permission=permission,
            scope_kind="chapter",
            scope_id=str(payload["chapter_id"]),
            actor=ARCHIVE_WORKER_ACTOR,
        )
    except AuthorityDenied:
        _record_authority_denied(effect, permission, db=db)
        return

    with db.transaction() as connection:
        application = applications_repo._get_application_on(
            connection,
            application_id=UUID(str(payload["target_id"])),
        )
        if (
            application is None
            or application["state"] not in _PENDING_APPLICATION_STATES
        ):
            return
        applications_service._transition_application_on(
            connection=connection,
            application_id=UUID(str(payload["target_id"])),
            expected_version=int(payload["expected_version"]),
            request=ApplicationTransitionRequest(
                action="withdraw",
                notes=f"chapter archived: {payload['archive_reason']}",
            ),
            actor=ARCHIVE_WORKER_ACTOR,
        )


@register_scheduler_handler(ARCHIVE_EFFECT_TICKET_CLOSE)
def handle_archive_ticket_close(
    effect: DeferredEffectRead,
    *,
    db: PostgresDatabase,
) -> None:
    tickets_repo = TicketsRepository(db)
    chapters_service = _build_chapters_service(db)
    payload = effect.payload_json
    permission = "ticket.transition"
    try:
        chapters_service.ensure_actor_has(
            permission=permission,
            scope_kind="chapter",
            scope_id=str(payload["chapter_id"]),
            actor=ARCHIVE_WORKER_ACTOR,
        )
    except AuthorityDenied:
        _record_authority_denied(effect, permission, db=db)
        return

    with db.connection() as connection:
        ticket = tickets_repo._get_ticket_on(
            connection, UUID(str(payload["target_id"]))
        )
    if ticket is None or ticket["terminal_at"] is not None:
        return
    close_edge = _find_close_edge(ticket)
    if close_edge is None:
        chapters_service.record_archive_manual_review_items(
            archive_run_id=UUID(str(payload["archive_run_id"])),
            items=[
                _manual_item(
                    kind="ticket",
                    item_id=str(payload["target_id"]),
                    reason="ticket_requires_manual_review",
                    metadata={"state": ticket["state"]},
                )
            ],
        )
        return
    _build_tickets_service(db).transition_ticket(
        UUID(str(payload["target_id"])),
        int(payload["expected_version"]),
        TicketTransitionRequest(
            action=str(close_edge["action"]),
            to_state=str(_edge_value(close_edge, "to")),
            reason=f"chapter archived: {payload['archive_reason']}",
            resolution="chapter_archived",
            originating_actor_kind="service",
            originating_actor_id=CHAPTER_ARCHIVER_ID,
        ),
        ARCHIVE_WORKER_ACTOR,
    )


@register_scheduler_handler(ARCHIVE_EFFECT_AUTHORITY_REVOKE)
def handle_archive_authority_revoke(
    effect: DeferredEffectRead,
    *,
    db: PostgresDatabase,
) -> None:
    chapters_service = _build_chapters_service(db)
    payload = effect.payload_json
    permission = "authority.revoke"
    try:
        chapters_service.ensure_actor_has(
            permission=permission,
            scope_kind="chapter",
            scope_id=str(payload["chapter_id"]),
            actor=ARCHIVE_WORKER_ACTOR,
        )
    except AuthorityDenied:
        _record_authority_denied(effect, permission, db=db)
        return

    with db.connection() as connection:
        grant = AuthorityRepository(db)._fetch_grant_on(
            connection,
            grant_id=UUID(str(payload["target_id"])),
        )
    if grant is None or grant["revoked_at"] is not None:
        return
    if grant["expires_at"] is not None and grant["expires_at"] <= current_time():
        return
    authority_service = AuthorityService(
        authority_repo=AuthorityRepository(db),
        members_repo=MembersRepository(db),
        roster_repo=RosterRepository(db),
        chapter_roles_repo=ChapterRolesRepository(db),
        applications_repo=ApplicationsRepository(db),
        tickets_repo=TicketsRepository(db),
        mutations_callable=partial(mutate_entity, db=db),
    )
    authority_service.revoke_authority(
        grant_id=UUID(str(payload["target_id"])),
        actor=(ARCHIVE_WORKER_ACTOR.actor_kind, ARCHIVE_WORKER_ACTOR.actor_id),
        revoked_by=CHAPTER_ARCHIVER_ID,
        reason=f"chapter archived: {payload['archive_reason']}",
        expected_version=int(payload["expected_version"]),
    )


@register_scheduler_handler(ARCHIVE_EFFECT_DEFERRED_EFFECT_CANCEL)
def handle_archive_deferred_effect_cancel(
    effect: DeferredEffectRead,
    *,
    db: PostgresDatabase,
) -> None:
    payload = effect.payload_json
    deferred_effects_repo = DeferredEffectsRepository(db)
    with db.connection() as connection:
        deferred_effects_repo._mark_unclaimed_deferred_effect_skipped_on(
            connection,
            effect_id=UUID(str(payload["target_id"])),
            reason=f"chapter archived: {payload['archive_reason']}",
        )


__all__ = [
    "ARCHIVE_TICK_INTERVAL_SECONDS",
    "ARCHIVE_WORKER_ACTOR",
    "CHAPTER_ARCHIVER_ID",
    "archive_worker_tick",
]
