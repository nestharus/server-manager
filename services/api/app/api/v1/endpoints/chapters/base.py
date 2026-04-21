"""Base chapter lifecycle endpoints."""

from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.chapter_templates import ChapterTemplateNotFoundError
from app.contracts.chapters import (
    ChapterArchiveInProgressError,
    ChapterArchivePrerequisitesError,
    ChapterCreate,
    ChapterDuplicateNameError,
    ChapterNotFoundError,
    ChapterRead,
    ChapterResourcesPatchRequest,
    ChapterTransitionRequest,
    IncompleteProvisioningError,
    InvalidChapterGovernanceTransitionError,
    InvalidChapterTransitionError,
)
from app.contracts.mutations import MissingAggregateError, StaleMutationError
from app.core.dependencies import RequireAuthority, get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.chapters import (
    create_chapter as create_chapter_service,
    patch_chapter_discord_resources,
    read_chapter as read_chapter_service,
    transition_chapter,
)

router = APIRouter(prefix="/api/v1/chapters")


def get_db(request: Request) -> PostgresDatabase:
    return request.app.state.db


def parse_if_match(request: Request) -> int:
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


def set_etag(response: Response, etag: str) -> None:
    response.headers["etag"] = etag


def raise_for_chapter_error(error: Exception) -> None:
    if isinstance(error, (ChapterNotFoundError, ChapterTemplateNotFoundError, MissingAggregateError)):
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="not found") from error
    if isinstance(error, StaleMutationError):
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail="Precondition Failed",
        ) from error
    if isinstance(error, ChapterDuplicateNameError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={"code": "duplicate_chapter_name", "name": error.name},
        ) from error
    if isinstance(error, InvalidChapterTransitionError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "invalid_transition",
                "from_state": error.from_state,
                "to_state": error.to_state,
            },
        ) from error
    if isinstance(error, InvalidChapterGovernanceTransitionError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "invalid_chapter_governance_transition",
                "action": error.action,
                "from_state": error.from_state,
                "to_state": error.to_state,
            },
        ) from error
    if isinstance(error, ChapterArchiveInProgressError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "chapter_archive_in_progress",
                "archive_run_id": str(error.archive_run_id),
                "correlation_id": str(error.correlation_id),
            },
        ) from error
    if isinstance(error, ChapterArchivePrerequisitesError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "chapter_archive_prerequisites_blocked",
                "chapter_id": error.chapter_id,
                "state": error.state,
            },
        ) from error
    if isinstance(error, IncompleteProvisioningError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={"code": "incomplete_provisioning", "missing": error.missing},
        ) from error
    raise error


@router.post(
    "",
    response_model=ChapterRead,
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(RequireAuthority("chapter.write", "global"))],
)
def create_chapter(
    chapter: ChapterCreate,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ChapterRead:
    try:
        read, result = create_chapter_service(db, chapter, actor)
    except Exception as error:
        raise_for_chapter_error(error)
    set_etag(response, result.etag)
    return read


@router.get(
    "/{chapter_id}",
    response_model=ChapterRead,
    dependencies=[Depends(RequireAuthority("chapter.read", "global"))],
)
def get_chapter(
    chapter_id: UUID,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
) -> ChapterRead:
    try:
        read, etag = read_chapter_service(db, str(chapter_id))
    except Exception as error:
        raise_for_chapter_error(error)
    set_etag(response, etag)
    return read


@router.post(
    "/{chapter_id}/transitions",
    response_model=ChapterRead,
    dependencies=[Depends(RequireAuthority("chapter.write", "global"))],
)
def transition_chapter_endpoint(
    chapter_id: UUID,
    transition: ChapterTransitionRequest,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ChapterRead:
    expected_version = parse_if_match(request)
    try:
        read, result = transition_chapter(
            db,
            str(chapter_id),
            transition,
            actor,
            expected_version,
        )
    except Exception as error:
        raise_for_chapter_error(error)
    set_etag(response, result.etag)
    return read


@router.patch(
    "/{chapter_id}/discord-resources",
    response_model=ChapterRead,
    dependencies=[Depends(RequireAuthority("chapter.write", "global"))],
)
def patch_chapter_discord_resources_endpoint(
    chapter_id: UUID,
    resources: ChapterResourcesPatchRequest,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ChapterRead:
    expected_version = parse_if_match(request)
    try:
        read, result = patch_chapter_discord_resources(
            db,
            str(chapter_id),
            resources,
            actor,
            expected_version,
        )
    except Exception as error:
        raise_for_chapter_error(error)
    set_etag(response, result.etag)
    return read


__all__ = [
    "get_db",
    "parse_if_match",
    "raise_for_chapter_error",
    "router",
    "set_etag",
]
