from __future__ import annotations

from functools import partial
from uuid import UUID

from app.contracts.actor import ActorIdentity
from app.contracts.applications import (
    ApplicationAlreadyClaimedError,
    ApplicationNotFoundError,
    ApplicationNotOwnerError,
    ApplicationTransitionRequest,
    InvalidApplicationTransitionError,
)
from app.contracts.authority import HandoffFailure, HandoffResult, LeadershipHandoffRequest
from app.contracts.mutations import StaleMutationError
from app.core.settings import Settings
from app.repositories.application_messages import ApplicationMessagesRepository
from app.repositories.applications import ApplicationsRepository
from app.repositories.db import PostgresDatabase
from app.repositories.forms import FormsRepository
from app.repositories.public_chapters import PublicChaptersRepository
from app.services.applications import ApplicationsService
from app.services.authority import (
    OPEN_APPLICATION_STATES,
    _collect_member_aliases,
    _normalize_holder_id,
    _require_scoped_authority,
    get_authority_grant,
)
from app.services.file_upload import FileUploadService, build_s3_client
from app.services.mutations import mutate_entity


def _build_applications_service(db: PostgresDatabase) -> ApplicationsService:
    settings = Settings()
    return ApplicationsService(
        applications_repo=ApplicationsRepository(db),
        application_messages_repo=ApplicationMessagesRepository(db),
        forms_repo=FormsRepository(db),
        public_chapters_repo=PublicChaptersRepository(db),
        file_upload_service=FileUploadService(
            s3_client=build_s3_client(settings),
            settings=settings,
        ),
        mutations_callable=partial(mutate_entity, db=db),
        notification_emitter=None,  # handoff does not trigger public submit
    )


def _failure_reason(error: Exception) -> str:
    if isinstance(error, (StaleMutationError, ApplicationAlreadyClaimedError)):
        return "occ_conflict"
    if isinstance(error, PermissionError):
        return "unauthorized"
    if isinstance(
        error,
        (
            ApplicationNotFoundError,
            ApplicationNotOwnerError,
            InvalidApplicationTransitionError,
            ValueError,
        ),
    ):
        return "invalid_state"
    raise error


def execute_handoff(
    db: PostgresDatabase,
    *,
    grant_id: UUID,
    request: LeadershipHandoffRequest,
    actor: ActorIdentity,
) -> HandoffResult:
    grant, _etag = get_authority_grant(db, grant_id=grant_id)
    _require_scoped_authority(
        "leadership_handoff.execute",
        scope_kind=grant.scope_kind,
        scope_id=grant.scope_id,
        actor=actor,
        db=db,
    )
    successor_member_id = _normalize_holder_id(
        request.successor_member_id,
        field_name="successor_member_id",
    )

    with db.connection() as connection:
        _predecessor_aliases, predecessor_uuid_aliases = _collect_member_aliases(
            connection,
            [grant.grantee_id],
        )
        _successor_aliases, successor_uuid_aliases = _collect_member_aliases(
            connection,
            [successor_member_id],
        )
        if not successor_uuid_aliases:
            raise ValueError(
                "successor_member_id must resolve to a member UUID for application handoff"
            )
        application_rows = ApplicationsRepository(db)._list_open_applications_for_owner_ids_on(
            connection,
            owner_ids=sorted(
                set(predecessor_uuid_aliases) | set(successor_uuid_aliases),
                key=str,
            ),
            states=sorted(OPEN_APPLICATION_STATES),
            scope_kind=grant.scope_kind,
            scope_id=grant.scope_id,
        )

    transferred: list[UUID] = []
    already_owned: list[UUID] = []
    failed: list[HandoffFailure] = []
    successor_uuid = sorted(successor_uuid_aliases, key=str)[0]
    applications_service = _build_applications_service(db)

    for row in application_rows:
        owner_id = row["owner_id"]
        if owner_id in successor_uuid_aliases:
            already_owned.append(row["id"])
            continue
        if owner_id not in predecessor_uuid_aliases:
            continue
        try:
            applications_service.transition_application(
                application_id=row["id"],
                expected_version=int(row["version"]),
                request=ApplicationTransitionRequest(
                    action="reassign",
                    new_owner_id=successor_uuid,
                    originating_actor_kind=actor.actor_kind,
                    originating_actor_id=actor.actor_id,
                ),
                actor=actor,
                request_surface=f"service:authority-grants/{grant_id}/handoff/applications",
                skip_authority_check=True,
            )
        except Exception as error:
            failed.append(
                HandoffFailure(
                    item_id=row["id"],
                    reason=_failure_reason(error),  # type: ignore[arg-type]
                    detail=str(error),
                )
            )
            continue
        transferred.append(row["id"])

    return HandoffResult(
        transferred=transferred,
        already_owned=already_owned,
        failed=failed,
    )
