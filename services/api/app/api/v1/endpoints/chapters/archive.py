from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.api.v1.endpoints.chapters.base import (
    get_db,
    parse_if_match,
    raise_for_chapter_error,
    set_etag,
)
from app.contracts.actor import ActorIdentity
from app.contracts.chapters import (
    ChapterArchiveExecuteRequest,
    ChapterArchivePlanRead,
    ChapterArchiveStatusRead,
)
from app.core.dependencies import RequireAuthority, get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.chapters import (
    archive_status as archive_status_service,
    build_archive_plan,
    execute_archive,
)

router = APIRouter(prefix="/api/v1/chapters")


@router.get(
    "/{chapter_id}/archive-plan",
    response_model=ChapterArchivePlanRead,
    dependencies=[
        Depends(RequireAuthority("chapter.archive_plan.read", "chapter", "chapter_id"))
    ],
)
def archive_plan(
    chapter_id: UUID,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ChapterArchivePlanRead:
    try:
        return build_archive_plan(db, str(chapter_id), actor)
    except Exception as error:
        raise_for_chapter_error(error)


@router.get(
    "/{chapter_id}/archive-status",
    response_model=ChapterArchiveStatusRead,
    dependencies=[
        Depends(RequireAuthority("chapter.archive_plan.read", "chapter", "chapter_id"))
    ],
)
def archive_status(
    chapter_id: UUID,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ChapterArchiveStatusRead:
    try:
        return archive_status_service(db, str(chapter_id), actor)
    except Exception as error:
        raise_for_chapter_error(error)


@router.post(
    "/{chapter_id}/archive-execute",
    response_model=ChapterArchiveStatusRead,
    dependencies=[Depends(RequireAuthority("chapter.archive", "chapter", "chapter_id"))],
)
def archive_execute(
    chapter_id: UUID,
    archive_request: ChapterArchiveExecuteRequest,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ChapterArchiveStatusRead:
    expected_version = parse_if_match(request)
    try:
        status, result = execute_archive(
            db,
            str(chapter_id),
            expected_version,
            archive_request,
            actor,
        )
    except Exception as error:
        raise_for_chapter_error(error)
    set_etag(response, result.etag)
    return status


__all__ = ["router"]
