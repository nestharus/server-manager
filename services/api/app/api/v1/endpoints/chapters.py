"""Chapter endpoints with ETag/If-Match concurrency."""

from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.contracts.chapters import ChapterCreate, ChapterRead, ChapterUpdate
from app.core.dependencies import get_chapter_service
from app.repositories.chapters import ChapterNotFoundError, StalePreconditionError
from app.services.chapters import ChapterService

router = APIRouter(prefix="/api/v1/chapters")


def _raise_for_chapter_error(error: Exception) -> None:
    if isinstance(error, ChapterNotFoundError):
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND) from error
    if isinstance(error, StalePreconditionError):
        raise HTTPException(
            status_code=412, detail="Precondition Failed",
        ) from error
    raise error


def _require_if_match(request: Request) -> str:
    if_match = request.headers.get("if-match")
    if if_match is None:
        raise HTTPException(
            status_code=428, detail="If-Match header required",
        )
    return if_match


@router.post("", response_model=ChapterRead, status_code=HTTPStatus.CREATED)
def create_chapter(
    chapter: ChapterCreate,
    response: Response,
    service: ChapterService = Depends(get_chapter_service),
) -> ChapterRead:
    read, etag = service.create_chapter(chapter)
    response.headers["etag"] = etag
    return read


@router.get("", response_model=list[ChapterRead])
def list_chapters(
    service: ChapterService = Depends(get_chapter_service),
) -> list[ChapterRead]:
    return service.list_chapters()


@router.get("/{chapter_id}", response_model=ChapterRead)
def get_chapter(
    chapter_id: int,
    response: Response,
    service: ChapterService = Depends(get_chapter_service),
) -> ChapterRead:
    try:
        read, etag = service.get_chapter(chapter_id)
    except Exception as error:
        _raise_for_chapter_error(error)
    response.headers["etag"] = etag
    return read


@router.patch("/{chapter_id}", response_model=ChapterRead)
def update_chapter(
    chapter_id: int,
    chapter: ChapterUpdate,
    request: Request,
    response: Response,
    service: ChapterService = Depends(get_chapter_service),
) -> ChapterRead:
    expected_head = _require_if_match(request)
    try:
        read, etag = service.update_chapter(
            chapter_id, chapter, expected_head=expected_head,
        )
    except Exception as error:
        _raise_for_chapter_error(error)
    response.headers["etag"] = etag
    return read


@router.post("/{chapter_id}/archive", response_model=ChapterRead)
def archive_chapter(
    chapter_id: int,
    request: Request,
    response: Response,
    service: ChapterService = Depends(get_chapter_service),
) -> ChapterRead:
    expected_head = _require_if_match(request)
    try:
        read, etag = service.archive_chapter(
            chapter_id, expected_head=expected_head,
        )
    except Exception as error:
        _raise_for_chapter_error(error)
    response.headers["etag"] = etag
    return read
