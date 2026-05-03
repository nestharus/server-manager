from __future__ import annotations

from functools import partial
from http import HTTPStatus
from typing import NoReturn
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.api.v1.endpoints.applications._shared import (
    parse_if_match_strong,
    raise_known_application_error,
    set_etag,
)
from app.api.v1.endpoints.me import get_pomerium_principal
from app.contracts.actor import ActorIdentity
from app.contracts.application_messages import (
    ApplicationMessageAppendForbiddenError,
    ApplicationMessageAppendRequest,
    ApplicationMessageForbiddenError,
    ApplicationMessageRead,
    ApplicationMessageVisibilityError,
)
from app.contracts.applications import (
    ApplicationAlreadyClaimedError,
    ApplicationListForbiddenError,
    ApplicationListRead,
    ApplicationNotFoundError,
    ApplicationNotOwnerError,
    ApplicationRead,
    ApplicationState,
    ApplicationTransitionAction,
    ApplicationTransitionRequest,
    DuplicateApplicationCreateError,
    InvalidApplicationTransitionError,
)
from app.contracts.applications_transcript import ApplicationTranscriptRead
from app.contracts.mutations import MissingAggregateError, StaleMutationError
from app.contracts.web import (
    AdminChapterListRead,
    CurrentPrincipalRead,
    OfficerApplicationMessageAppendRequest,
)
from app.core.container import ApiContainer
from app.repositories.db import PostgresDatabase
from app.repositories.members import MembersRepository
from app.services.applicant_discord_auth import DISCORD_SNOWFLAKE_RE
from app.services.application_messages import ApplicationMessagesService
from app.services.application_transcript import ApplicationTranscriptService
from app.services.applications import ApplicationsService
from app.services.members import MembersService, NonDiscordMemberError
from app.services.mutations import mutate_entity
from app.services.web import list_web_admin_chapters


router = APIRouter(prefix="/api/v1/web")


def _db(request: Request) -> PostgresDatabase:
    return request.app.state.db


@router.get("/admin/chapters", response_model=AdminChapterListRead)
def admin_chapters(
    _principal: CurrentPrincipalRead = Depends(get_pomerium_principal),
    db: PostgresDatabase = Depends(_db),
) -> AdminChapterListRead:
    return list_web_admin_chapters(db)


def _parse_state_query(state: str | None) -> frozenset[str] | None:
    if state is None:
        return None
    parsed: set[str] = set()
    valid_states = {item.value for item in ApplicationState}
    for raw_state in state.split(","):
        value = raw_state.strip()
        if not value:
            continue
        if value not in valid_states:
            raise ValueError(f"invalid application state: {value}")
        parsed.add(value)
    return frozenset(parsed)


async def _build_officer_actor(
    request: Request,
    db: PostgresDatabase,
    *,
    request_surface: str,
) -> ActorIdentity:
    principal = get_pomerium_principal(request)
    if "officers" not in principal.groups:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={
                "code": "officer_required",
                "message": "Officer group membership is required.",
            },
        )

    discord_user_id = principal.discord_user_id
    if discord_user_id is None or not discord_user_id.strip():
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail={
                "code": "officer_discord_identity_missing",
                "message": "Officer Discord identity claim is required.",
            },
        )
    discord_user_id = discord_user_id.strip()
    if not DISCORD_SNOWFLAKE_RE.match(discord_user_id):
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail={
                "code": "officer_discord_identity_invalid",
                "message": "Officer Discord identity claim must be a Discord snowflake.",
            },
        )

    try:
        member = await MembersService(
            members_repo=MembersRepository(db),
            mutations_callable=partial(mutate_entity, db=db),
        ).resolve_or_create_real_discord_member(
            discord_user_id=discord_user_id,
            originating_actor=ActorIdentity(
                actor_kind="service",
                actor_id="web-officer-bridge",
            ),
            request_surface=request_surface,
        )
    except NonDiscordMemberError as error:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={
                "code": "officer_discord_member_invalid",
                "message": "Officer Discord identity is bound to a non-discord member.",
            },
        ) from error

    return ActorIdentity(actor_kind="user", actor_id=str(member.id))


def get_officer_actor(request_surface: str):
    async def dependency(
        request: Request,
        db: PostgresDatabase = Depends(_db),
    ) -> ActorIdentity:
        return await _build_officer_actor(
            request,
            db,
            request_surface=request_surface.format(**request.path_params),
        )

    return dependency


def _raise_officer_application_message_error(error: Exception) -> NoReturn:
    if isinstance(error, ApplicationMessageVisibilityError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "applicant_visibility_required", "message": str(error)},
        ) from error
    if isinstance(error, ApplicationMessageAppendForbiddenError):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={"code": "application_message_forbidden", "message": str(error)},
        ) from error
    raise_known_application_error(error)


@router.get("/officer/applications", response_model=ApplicationListRead)
@inject
async def officer_list_applications(
    actor: ActorIdentity = Depends(
        get_officer_actor("api:/api/v1/web/officer/applications")
    ),
    service: ApplicationsService = Depends(Provide[ApiContainer.services.applications]),
    state: str | None = Query(None),
    scope_kind: str | None = Query(None),
    scope_id: str | None = Query(None),
    owner_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    after_id: UUID | None = Query(None),
) -> ApplicationListRead:
    try:
        states = _parse_state_query(state)
        return service.list_applications(
            actor=actor,
            states=states,
            scope_kind=scope_kind,
            scope_id=scope_id,
            owner_id=owner_id,
            limit=limit,
            after_id=after_id,
        )
    except (
        ApplicationListForbiddenError,
        ValueError,
        PermissionError,
    ) as error:
        raise_known_application_error(error)


@router.get("/officer/applications/{application_id}", response_model=ApplicationRead)
@inject
async def officer_read_application(
    application_id: UUID,
    actor: ActorIdentity = Depends(
        get_officer_actor("api:/api/v1/web/officer/applications/{application_id}")
    ),
    service: ApplicationsService = Depends(Provide[ApiContainer.services.applications]),
) -> ApplicationRead:
    try:
        read, _etag = service.read_application(application_id=application_id)
        service.require_application_read_authority(actor=actor, application=read)
        return read
    except (ApplicationNotFoundError, ValueError, PermissionError) as error:
        raise_known_application_error(error)


@router.post(
    "/officer/applications/{application_id}/claim",
    response_model=ApplicationRead,
)
@inject
async def officer_claim_application(
    application_id: UUID,
    request: Request,
    response: Response,
    actor: ActorIdentity = Depends(
        get_officer_actor("api:/api/v1/web/officer/applications")
    ),
    service: ApplicationsService = Depends(Provide[ApiContainer.services.applications]),
) -> ApplicationRead:
    expected_version = parse_if_match_strong(request)
    transition_request = ApplicationTransitionRequest(
        action=ApplicationTransitionAction.claim,
    )
    try:
        read, result = service.transition_application(
            actor=actor,
            application_id=application_id,
            expected_version=expected_version,
            request=transition_request,
            request_surface=(
                f"api:/api/v1/web/officer/applications/"
                f"{application_id}/claim"
            ),
        )
    except ApplicationAlreadyClaimedError as error:
        if error.application.version != expected_version:
            raise_known_application_error(
                StaleMutationError(
                    aggregate_type="application",
                    aggregate_id=str(application_id),
                    expected_version=expected_version,
                    current_version=error.application.version,
                ),
            )
        raise_known_application_error(error)
    except InvalidApplicationTransitionError as error:
        if error.action == "claim" and error.from_state == "claimed":
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail={
                    "code": "application_already_claimed",
                    "message": str(error),
                },
            ) from error
        raise_known_application_error(error)
    except (
        ApplicationNotFoundError,
        StaleMutationError,
        ApplicationNotOwnerError,
        MissingAggregateError,
        DuplicateApplicationCreateError,
        PermissionError,
    ) as error:
        raise_known_application_error(error)
    set_etag(response, result.etag)
    return read


@router.post(
    "/officer/applications/{application_id}/messages",
    response_model=ApplicationMessageRead,
    status_code=HTTPStatus.CREATED,
)
@inject
async def officer_append_application_message(
    application_id: UUID,
    response: Response,
    body: OfficerApplicationMessageAppendRequest,
    actor: ActorIdentity = Depends(
        get_officer_actor(
            "api:/api/v1/web/officer/applications/{application_id}/messages"
        )
    ),
    service: ApplicationMessagesService = Depends(
        Provide[ApiContainer.services.application_messages]
    ),
) -> ApplicationMessageRead:
    service_request = ApplicationMessageAppendRequest(
        body_markdown=body.body_markdown,
        visibility=body.visibility,
        client_message_id=body.client_message_id,
        author_actor_kind=actor.actor_kind,
        author_actor_id=actor.actor_id,
    )
    try:
        read, created = service.append_application_message(
            application_id=application_id,
            request=service_request,
        )
    except (
        ApplicationNotFoundError,
        ApplicationMessageAppendForbiddenError,
        ApplicationMessageVisibilityError,
        ValueError,
        PermissionError,
    ) as error:
        _raise_officer_application_message_error(error)
    response.status_code = HTTPStatus.CREATED if created else HTTPStatus.OK
    return read


@router.get(
    "/officer/applications/{application_id}/transcript",
    response_model=ApplicationTranscriptRead,
)
@inject
async def officer_read_application_transcript(
    application_id: UUID,
    actor: ActorIdentity = Depends(
        get_officer_actor(
            "api:/api/v1/web/officer/applications/{application_id}/transcript"
        )
    ),
    service: ApplicationTranscriptService = Depends(
        Provide[ApiContainer.services.application_transcript]
    ),
) -> ApplicationTranscriptRead:
    try:
        return service.read_application_transcript(
            application_id=application_id,
            viewer_actor_kind=actor.actor_kind,
            viewer_actor_id=actor.actor_id,
        )
    except (
        ApplicationNotFoundError,
        ApplicationMessageForbiddenError,
        ValueError,
        PermissionError,
    ) as error:
        raise_known_application_error(error)


@router.post(
    "/officer/applications/{application_id}/transitions",
    response_model=ApplicationRead,
)
@inject
async def officer_transition_application(
    application_id: UUID,
    request: Request,
    response: Response,
    body: ApplicationTransitionRequest,
    actor: ActorIdentity = Depends(
        get_officer_actor(
            "api:/api/v1/web/officer/applications/{application_id}/transitions"
        )
    ),
    service: ApplicationsService = Depends(Provide[ApiContainer.services.applications]),
) -> ApplicationRead:
    if body.action == ApplicationTransitionAction.claim:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail={
                "code": "claim_action_uses_dedicated_endpoint",
                "message": (
                    "Use POST /officer/applications/{id}/claim "
                    "for claim transitions."
                ),
            },
        )
    expected_version = parse_if_match_strong(request)
    try:
        read, result = service.transition_application(
            actor=actor,
            application_id=application_id,
            expected_version=expected_version,
            request=body,
            request_surface=(
                f"api:/api/v1/web/officer/applications/"
                f"{application_id}/transitions"
            ),
            allow_route_transition=True,
        )
    except (
        ApplicationNotFoundError,
        StaleMutationError,
        ApplicationAlreadyClaimedError,
        ApplicationNotOwnerError,
        InvalidApplicationTransitionError,
        MissingAggregateError,
        DuplicateApplicationCreateError,
        ValueError,
        PermissionError,
    ) as error:
        raise_known_application_error(error)
    set_etag(response, result.etag)
    return read
