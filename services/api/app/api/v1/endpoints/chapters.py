"""Chapter endpoint stubs."""

from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException

from app.contracts.chapters import ChapterCreate, ChapterRead, ChapterUpdate
from app.core.dependencies import get_chapter_service
from app.repositories.chapters import ChapterNotFoundError, ChapterVersionConflictError
from app.services.chapters import ChapterService

router = APIRouter(prefix="/api/v1/chapters")


def _raise_for_chapter_error(error: Exception) -> None:
    if isinstance(error, ChapterNotFoundError):
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND) from error
    if isinstance(error, ChapterVersionConflictError):
        raise HTTPException(status_code=HTTPStatus.CONFLICT) from error
    raise error


@router.post("", response_model=ChapterRead, status_code=HTTPStatus.CREATED)
def create_chapter(
    chapter: ChapterCreate,
    service: ChapterService = Depends(get_chapter_service),
) -> ChapterRead:
    return service.create_chapter(chapter)


@router.get("", response_model=list[ChapterRead])
def list_chapters(service: ChapterService = Depends(get_chapter_service)) -> list[ChapterRead]:
    return service.list_chapters()


@router.get("/{chapter_id}", response_model=ChapterRead)
def get_chapter(
    chapter_id: int,
    service: ChapterService = Depends(get_chapter_service),
) -> ChapterRead:
    try:
        return service.get_chapter(chapter_id)
    except Exception as error:
        _raise_for_chapter_error(error)


@router.patch("/{chapter_id}", response_model=ChapterRead)
def update_chapter(
    chapter_id: int,
    chapter: ChapterUpdate,
    service: ChapterService = Depends(get_chapter_service),
) -> ChapterRead:
    try:
        return service.update_chapter(chapter_id, chapter)
    except Exception as error:
        _raise_for_chapter_error(error)


@router.post("/{chapter_id}/archive", response_model=ChapterRead)
def archive_chapter(
    chapter_id: int,
    service: ChapterService = Depends(get_chapter_service),
) -> ChapterRead:
    try:
        return service.archive_chapter(chapter_id)
    except Exception as error:
        _raise_for_chapter_error(error)
