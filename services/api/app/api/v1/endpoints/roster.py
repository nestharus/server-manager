"""Roster lifecycle endpoints."""

from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.authority import AuthorityDecisionRead, AuthorityRequirement
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
from app.core.dependencies import RequireAuthority, get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.authority import current_time, evaluate, list_grants_for_grantee
from app.services.roster import (
    create_roster_entry as create_roster_entry_service,
    get_roster_entry as get_roster_entry_service,
    record_roster_sync_failure,
    transition_roster_entry,
)

router = APIRouter(prefix="/api/v1/roster-entries")


def get_db(request: Request) -> PostgresDatabase:
    return request.app.state.db


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
    db: PostgresDatabase,
    actor: ActorIdentity,
    permission: str,
    scope_kind: str,
    scope_id: str | None,
) -> AuthorityDecisionRead:
    requirement = AuthorityRequirement(
        scope_kind=scope_kind,
        scope_id=scope_id,
        permission=permission,
    )
    grants = list_grants_for_grantee(db, grantee_id=actor.actor_id)
    decision = evaluate(requirement=requirement, grants=grants, at=current_time())
    if not decision.allowed:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={
                "code": "authority_decision_denied",
                "message": "authority requirement denied",
                "decision": decision.model_dump(mode="json"),
            },
        )
    return decision


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
def create_roster_entry(
    roster_entry: RosterEntryCreate,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(_user_actor_only),
) -> RosterEntryRead:
    _require_authority(
        db=db,
        actor=actor,
        permission="roster.write",
        scope_kind="chapter",
        scope_id=roster_entry.chapter_id,
    )
    try:
        read, result = create_roster_entry_service(db, roster_entry, actor)
    except Exception as error:
        _raise_for_roster_error(error)
    _set_etag(response, result.etag)
    return read


@router.get("/{entry_id}", response_model=RosterEntryRead)
def get_roster_entry(
    entry_id: UUID,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(_user_actor_only),
) -> RosterEntryRead:
    try:
        read, etag = get_roster_entry_service(db, entry_id)
    except Exception as error:
        _raise_for_roster_error(error)
    _require_authority(
        db=db,
        actor=actor,
        permission="roster.read",
        scope_kind="chapter",
        scope_id=read.chapter_id,
    )
    _set_etag(response, etag)
    return read


@router.post("/{entry_id}/transitions", response_model=RosterEntryRead)
def transition_roster_entry_endpoint(
    entry_id: UUID,
    transition: RosterEntryTransitionRequest,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(_user_actor_only),
) -> RosterEntryRead:
    expected_version = _parse_if_match(request)
    try:
        current, _etag = get_roster_entry_service(db, entry_id)
    except Exception as error:
        _raise_for_roster_error(error)
    _require_authority(
        db=db,
        actor=actor,
        permission=("roster.remove" if transition.to_status == "removed" else "roster.write"),
        scope_kind="chapter",
        scope_id=current.chapter_id,
    )
    try:
        read, result = transition_roster_entry(
            db,
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
def record_sync_failure_endpoint(
    entry_id: UUID,
    failure: RosterSyncFailureRequest,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> RosterEntryRead:
    expected_version = _parse_if_match(request)
    try:
        read, result = record_roster_sync_failure(
            db,
            entry_id,
            failure,
            actor,
            expected_version,
        )
    except Exception as error:
        _raise_for_roster_error(error)
    _set_etag(response, result.etag)
    return read
