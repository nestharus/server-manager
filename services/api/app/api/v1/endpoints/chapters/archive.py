from __future__ import annotations

from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request, Response

from app.api.v1.endpoints.chapters.base import (
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
from app.core.container import ApiContainer
from app.core.dependencies import RequireAuthority, get_current_actor
from app.services.chapters import ChaptersService

router = APIRouter(prefix="/api/v1/chapters")


@router.get(
    "/{chapter_id}/archive-plan",
    response_model=ChapterArchivePlanRead,
    dependencies=[
        Depends(RequireAuthority("chapter.archive_plan.read", "chapter", "chapter_id"))
    ],
)
@inject
def archive_plan(
    chapter_id: UUID,
    service: ChaptersService = Depends(Provide[ApiContainer.services.chapters]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ChapterArchivePlanRead:
    try:
        return service.build_archive_plan(str(chapter_id), actor)
    except Exception as error:
        raise_for_chapter_error(error)


@router.get(
    "/{chapter_id}/archive-status",
    response_model=ChapterArchiveStatusRead,
    dependencies=[
        Depends(RequireAuthority("chapter.archive_plan.read", "chapter", "chapter_id"))
    ],
)
@inject
def archive_status(
    chapter_id: UUID,
    service: ChaptersService = Depends(Provide[ApiContainer.services.chapters]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ChapterArchiveStatusRead:
    try:
        return service.archive_status(str(chapter_id), actor)
    except Exception as error:
        raise_for_chapter_error(error)


@router.post(
    "/{chapter_id}/archive-execute",
    response_model=ChapterArchiveStatusRead,
    dependencies=[
        Depends(RequireAuthority("chapter.archive", "chapter", "chapter_id"))
    ],
)
@inject
def archive_execute(
    chapter_id: UUID,
    archive_request: ChapterArchiveExecuteRequest,
    request: Request,
    response: Response,
    service: ChaptersService = Depends(Provide[ApiContainer.services.chapters]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ChapterArchiveStatusRead:
    expected_version = parse_if_match(request)
    try:
        status, result = service.execute_archive(
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
