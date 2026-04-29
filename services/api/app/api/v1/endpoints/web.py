from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.api.v1.endpoints.applications._shared import (
    parse_if_match_strong,
    raise_known_application_error,
    set_etag,
)
from app.api.v1.endpoints.me import get_pomerium_principal
from app.contracts.actor import ActorIdentity
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
from app.contracts.mutations import MissingAggregateError, StaleMutationError
from app.contracts.web import AdminChapterListRead, CurrentPrincipalRead
from app.repositories.db import PostgresDatabase
from app.services.applicant_discord_auth import DISCORD_SNOWFLAKE_RE
from app.services.applications import list_applications, transition_application
from app.services.members import NonDiscordMemberError, resolve_or_create_real_discord_member
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


async def _build_officer_actor(request: Request, db: PostgresDatabase) -> ActorIdentity:
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
        member = await resolve_or_create_real_discord_member(
            db,
            discord_user_id=discord_user_id,
            originating_actor=ActorIdentity(
                actor_kind="service",
                actor_id="web-officer-bridge",
            ),
            request_surface="api:/api/v1/web/officer/applications",
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


@router.get("/officer/applications", response_model=ApplicationListRead)
async def officer_list_applications(
    request: Request,
    db: PostgresDatabase = Depends(_db),
    state: str | None = Query(None),
    scope_kind: str | None = Query(None),
    scope_id: str | None = Query(None),
    owner_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    after_id: UUID | None = Query(None),
) -> ApplicationListRead:
    actor = await _build_officer_actor(request, db)
    try:
        states = _parse_state_query(state)
        return list_applications(
            db,
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


@router.post(
    "/officer/applications/{application_id}/claim",
    response_model=ApplicationRead,
)
async def officer_claim_application(
    application_id: UUID,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(_db),
) -> ApplicationRead:
    actor = await _build_officer_actor(request, db)
    expected_version = parse_if_match_strong(request)
    transition_request = ApplicationTransitionRequest(
        action=ApplicationTransitionAction.claim,
    )
    try:
        read, result = transition_application(
            db,
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
