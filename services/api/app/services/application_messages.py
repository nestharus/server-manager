from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection

from app.contracts.application_messages import (
    APPLICATION_MESSAGE_PERMISSION,
    ApplicationMessageAppendForbiddenError,
    ApplicationMessageForbiddenError,
    ApplicationMessageAppendRequest,
    ApplicationMessageRead,
    ApplicationMessageVisibilityError,
)
from app.contracts.applications import ApplicationNotFoundError
from app.contracts.authority import AuthorityRequirement
from app.core.context import MissingCorrelationContextError, get_current_audit_context
from app.repositories.application_messages import (
    find_application_message_by_client_message_id,
    get_application_message,
    insert_application_message,
    list_application_messages,
    next_application_message_seq,
)
from app.repositories.applications import get_application, get_application_for_update
from app.repositories.db import PostgresDatabase
from app.services.authority import current_time, evaluate, list_grants_for_grantee


def _message_from_row(row: dict[str, Any]) -> ApplicationMessageRead:
    return ApplicationMessageRead(
        id=row["id"],
        application_id=row["application_id"],
        message_seq=int(row["message_seq"]),
        author_actor_kind=row["author_actor_kind"],
        author_actor_id=row["author_actor_id"],
        visibility=row["visibility"],
        body_markdown=row["body_markdown"],
        client_message_id=row["client_message_id"],
        correlation_id=row["correlation_id"],
        causation_id=row.get("causation_id"),
        created_at=row["created_at"],
    )


def _application_target_scope(application_row: dict[str, Any]) -> tuple[str, str | None]:
    target_scope = application_row["form_snapshot"]["target_scope"]
    return str(target_scope["scope_kind"]), target_scope.get("scope_id")


def _has_officer_authority(
    db: PostgresDatabase,
    *,
    application_row: dict[str, Any],
    actor_id: str,
) -> bool:
    scope_kind, scope_id = _application_target_scope(application_row)
    requirement = AuthorityRequirement(
        scope_kind=scope_kind,  # type: ignore[arg-type]
        scope_id=scope_id,
        permission=APPLICATION_MESSAGE_PERMISSION,
    )
    grants = list_grants_for_grantee(db, grantee_id=actor_id)
    decision = evaluate(requirement=requirement, grants=grants, at=current_time())
    return decision.allowed


def _assert_officer_authority(
    db: PostgresDatabase,
    *,
    application_row: dict[str, Any],
    author_actor_id: str,
) -> None:
    if not _has_officer_authority(
        db,
        application_row=application_row,
        actor_id=author_actor_id,
    ):
        raise ApplicationMessageAppendForbiddenError(
            "application.message authority denied"
        )


def append_application_message(
    db: PostgresDatabase,
    *,
    application_id: UUID,
    request: ApplicationMessageAppendRequest,
    connection: Connection[Any] | None = None,
) -> tuple[ApplicationMessageRead, bool]:
    def _append(active_connection: Connection[Any]) -> tuple[ApplicationMessageRead, bool]:
        if request.client_message_id:
            existing = find_application_message_by_client_message_id(
                active_connection,
                application_id=application_id,
                client_message_id=request.client_message_id,
            )
            if existing is not None:
                return _message_from_row(existing), False

        application_row = get_application_for_update(
            active_connection,
            application_id=application_id,
        )
        if application_row is None:
            raise ApplicationNotFoundError(application_id)

        applicant_id = str(application_row["applicant_id"])
        is_applicant_authored = (
            request.author_actor_kind == "user"
            and request.author_actor_id == applicant_id
        )

        if is_applicant_authored:
            if request.visibility != "applicant_visible":
                raise ApplicationMessageVisibilityError(
                    "applicant-authored messages must be applicant_visible"
                )
        else:
            _assert_officer_authority(
                db,
                application_row=application_row,
                author_actor_id=request.author_actor_id,
            )

        ctx = get_current_audit_context()
        if ctx is None:
            raise MissingCorrelationContextError()

        message_id = uuid4()
        insert_application_message(
            active_connection,
            row={
                "id": message_id,
                "application_id": application_id,
                "message_seq": next_application_message_seq(
                    active_connection,
                    application_id=application_id,
                ),
                "author_actor_kind": request.author_actor_kind,
                "author_actor_id": request.author_actor_id,
                "visibility": request.visibility,
                "body_markdown": request.body_markdown,
                "client_message_id": request.client_message_id,
                "correlation_id": ctx.correlation_id,
                "causation_id": ctx.causation_id,
            },
        )
        row = get_application_message(active_connection, message_id)
        if row is None:
            raise RuntimeError("application message insert did not return a readable row")
        return _message_from_row(row), True

    if connection is not None:
        return _append(connection)
    with db.transaction() as active_connection:
        return _append(active_connection)


def read_application_messages(
    db: PostgresDatabase,
    *,
    application_id: UUID,
    viewer_actor_kind: str,
    viewer_actor_id: str,
) -> list[ApplicationMessageRead]:
    with db.connection() as connection:
        application_row = get_application(
            connection,
            application_id=application_id,
        )
        if application_row is None:
            raise ApplicationNotFoundError(application_id)

        applicant_id = str(application_row["applicant_id"])
        is_applicant_viewer = (
            viewer_actor_kind == "user" and viewer_actor_id == applicant_id
        )
        can_view_officer_only = _has_officer_authority(
            db,
            application_row=application_row,
            actor_id=viewer_actor_id,
        )
        if not is_applicant_viewer and not can_view_officer_only:
            raise ApplicationMessageForbiddenError(
                "application.message authority denied"
            )

        messages = [
            _message_from_row(row)
            for row in list_application_messages(
                connection,
                application_id=application_id,
            )
        ]
        if is_applicant_viewer and not can_view_officer_only:
            return [
                message
                for message in messages
                if message.visibility == "applicant_visible"
            ]
        return messages


__all__ = [
    "append_application_message",
    "read_application_messages",
]
