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
from app.repositories.application_messages import ApplicationMessagesRepository
from app.repositories.applications import ApplicationsRepository
from app.repositories.authority import AuthorityRepository
from app.repositories.db import PostgresDatabase
from app.services.authority import current_time, evaluate, _row_to_read


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
    authority_repo = AuthorityRepository(db)
    grants = [
        _row_to_read(row)
        for row in authority_repo.list_grants(
            grantee_id=actor_id,
            include_revoked=True,
            limit=None,
            after_id=None,
        )
    ]
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


class ApplicationMessagesService:
    def __init__(
        self,
        applications_repo: ApplicationsRepository,
        application_messages_repo: ApplicationMessagesRepository,
        mutations_callable,
    ) -> None:
        self._applications_repo = applications_repo
        self._application_messages_repo = application_messages_repo
        self._mutations_callable = mutations_callable

    def append_application_message(
        self,
        *,
        application_id: UUID,
        request: ApplicationMessageAppendRequest,
    ) -> tuple[ApplicationMessageRead, bool]:
        with self._applications_repo.db.transaction() as connection:
            return self._append_application_message_on(
                connection,
                application_id=application_id,
                request=request,
            )

    def _append_application_message_on(
        self,
        connection: Connection[Any],
        application_id: UUID,
        request: ApplicationMessageAppendRequest,
    ) -> tuple[ApplicationMessageRead, bool]:
        if request.client_message_id:
            existing = self._application_messages_repo._find_application_message_by_client_message_id_on(
                connection,
                application_id=application_id,
                client_message_id=request.client_message_id,
            )
            if existing is not None:
                return _message_from_row(existing), False

        application_row = self._applications_repo._get_application_for_update_on(
            connection,
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
                self._applications_repo.db,
                application_row=application_row,
                author_actor_id=request.author_actor_id,
            )

        ctx = get_current_audit_context()
        if ctx is None:
            raise MissingCorrelationContextError()

        message_id = uuid4()
        self._application_messages_repo._insert_application_message_on(
            connection,
            row={
                "id": message_id,
                "application_id": application_id,
                "message_seq": self._application_messages_repo._next_application_message_seq_on(
                    connection,
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
        row = self._application_messages_repo._get_application_message_on(
            connection,
            message_id,
        )
        if row is None:
            raise RuntimeError("application message insert did not return a readable row")
        return _message_from_row(row), True

    def read_application_messages(
        self,
        *,
        application_id: UUID,
        viewer_actor_kind: str,
        viewer_actor_id: str,
    ) -> list[ApplicationMessageRead]:
        with self._applications_repo.db.connection() as connection:
            application_row = self._applications_repo._get_application_on(
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
                self._applications_repo.db,
                application_row=application_row,
                actor_id=viewer_actor_id,
            )
            if not is_applicant_viewer and not can_view_officer_only:
                raise ApplicationMessageForbiddenError(
                    "application.message authority denied"
                )

            messages = [
                _message_from_row(row)
                for row in self._application_messages_repo._list_application_messages_on(
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


__all__ = ["ApplicationMessagesService"]
