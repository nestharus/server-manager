"""Roster lifecycle endpoints."""

from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.mutations import MissingAggregateError, StaleMutationError
from app.contracts.roster import (
    InvalidRosterStatusTransitionError,
    RosterDuplicateCurrentEntryError,
    RosterEntryCreate,
    RosterEntryNotFoundError,
    RosterEntryRead,
    RosterEntryTransitionRequest,
    RosterRoleChapterMismatchError,
    RosterRoleNotFoundError,
    RosterSyncFailureRequest,
)
from app.core.container import ApiContainer
from app.core.dependencies import RequireAuthority, get_current_actor
from app.services.authority import AuthorityService
from app.services.roster import RosterService

router = APIRouter(prefix="/api/v1/roster-entries")


def _parse_if_match(request: Request) -> int:
    if_match = request.headers.get("if-match")
    if if_match is None:
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_REQUIRED,
            detail="If-Match header required",
        )
    if not (if_match.startswith('"') and if_match.endswith('"')):
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="invalid If-Match")
    try:
        return int(if_match.strip('"'))
    except ValueError as error:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="invalid If-Match") from error


def _set_etag(response: Response, etag: str) -> None:
    response.headers["etag"] = etag


def _forbidden(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=HTTPStatus.FORBIDDEN, detail={"code": code, "message": message})


def _user_actor_only(actor: ActorIdentity = Depends(get_current_actor)) -> ActorIdentity:
    if actor.actor_kind != "user":
        raise _forbidden("user_actor_required", "operator roster endpoints require a user actor")
    return actor


def _service_actor_only(actor: ActorIdentity = Depends(get_current_actor)) -> ActorIdentity:
    if actor.actor_kind != "service":
        raise _forbidden("service_actor_required", "sync failure reporting requires a service actor")
    if actor.actor_id != "roster-syncer":
        raise _forbidden("roster_syncer_required", "sync failure reporting requires roster-syncer")
    return actor


def _require_authority(
    *,
    authority_service: AuthorityService,
    actor: ActorIdentity,
    permission: str,
    scope_kind: str,
    scope_id: str | None,
) -> None:
    try:
        authority_service.require_scoped_authority(
            permission,
            scope_kind=scope_kind,
            scope_id=scope_id,
            actor=actor,
        )
    except PermissionError as error:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={
                "code": "authority_decision_denied",
                "message": "authority requirement denied",
            },
        ) from error


def _raise_for_roster_error(error: Exception) -> None:
    if isinstance(error, (RosterEntryNotFoundError, RosterRoleNotFoundError, MissingAggregateError)):
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="not found") from error
    if isinstance(error, StaleMutationError):
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail="Precondition Failed",
        ) from error
    if isinstance(error, RosterDuplicateCurrentEntryError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "duplicate_current_roster_entry",
                "chapter_id": error.chapter_id,
                "member_id": error.member_id,
            },
        ) from error
    if isinstance(error, InvalidRosterStatusTransitionError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "invalid_roster_transition",
                "from_status": error.current_status,
                "to_status": error.new_status,
            },
        ) from error
    if isinstance(error, RosterRoleChapterMismatchError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "roster_role_chapter_mismatch",
                "role_id": str(error.role_id),
                "chapter_id": error.chapter_id,
            },
        ) from error
    raise error


@router.post("", response_model=RosterEntryRead, status_code=HTTPStatus.CREATED)
@inject
def create_roster_entry(
    roster_entry: RosterEntryCreate,
    response: Response,
    service: RosterService = Depends(Provide[ApiContainer.services.roster]),
    authority_service: AuthorityService = Depends(Provide[ApiContainer.services.authority]),
    actor: ActorIdentity = Depends(_user_actor_only),
) -> RosterEntryRead:
    _require_authority(
        authority_service=authority_service,
        actor=actor,
        permission="roster.write",
        scope_kind="chapter",
        scope_id=roster_entry.chapter_id,
    )
    try:
        read, result = service.create_roster_entry(roster_entry, actor)
    except Exception as error:
        _raise_for_roster_error(error)
    _set_etag(response, result.etag)
    return read


@router.get("/{entry_id}", response_model=RosterEntryRead)
@inject
def get_roster_entry(
    entry_id: UUID,
    response: Response,
    service: RosterService = Depends(Provide[ApiContainer.services.roster]),
    authority_service: AuthorityService = Depends(Provide[ApiContainer.services.authority]),
    actor: ActorIdentity = Depends(_user_actor_only),
) -> RosterEntryRead:
    try:
        read, etag = service.get_roster_entry(entry_id)
    except Exception as error:
        _raise_for_roster_error(error)
    _require_authority(
        authority_service=authority_service,
        actor=actor,
        permission="roster.read",
        scope_kind="chapter",
        scope_id=read.chapter_id,
    )
    _set_etag(response, etag)
    return read


@router.post("/{entry_id}/transitions", response_model=RosterEntryRead)
@inject
def transition_roster_entry_endpoint(
    entry_id: UUID,
    transition: RosterEntryTransitionRequest,
    request: Request,
    response: Response,
    service: RosterService = Depends(Provide[ApiContainer.services.roster]),
    authority_service: AuthorityService = Depends(Provide[ApiContainer.services.authority]),
    actor: ActorIdentity = Depends(_user_actor_only),
) -> RosterEntryRead:
    expected_version = _parse_if_match(request)
    try:
        current, _etag = service.get_roster_entry(entry_id)
    except Exception as error:
        _raise_for_roster_error(error)
    _require_authority(
        authority_service=authority_service,
        actor=actor,
        permission=("roster.remove" if transition.to_status == "removed" else "roster.write"),
        scope_kind="chapter",
        scope_id=current.chapter_id,
    )
    try:
        read, result = service.transition_roster_entry(
            entry_id,
            transition,
            actor,
            expected_version,
        )
    except Exception as error:
        _raise_for_roster_error(error)
    _set_etag(response, result.etag)
    return read


@router.post(
    "/{entry_id}/sync-failure",
    response_model=RosterEntryRead,
    dependencies=[Depends(_service_actor_only), Depends(RequireAuthority("roster.write", "global"))],
)
@inject
def record_sync_failure_endpoint(
    entry_id: UUID,
    failure: RosterSyncFailureRequest,
    request: Request,
    response: Response,
    service: RosterService = Depends(Provide[ApiContainer.services.roster]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> RosterEntryRead:
    expected_version = _parse_if_match(request)
    try:
        read, result = service.record_roster_sync_failure(
            entry_id,
            failure,
            actor,
            expected_version,
        )
    except Exception as error:
        _raise_for_roster_error(error)
    _set_etag(response, result.etag)
    return read
