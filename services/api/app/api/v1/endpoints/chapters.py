"""Chapter endpoint stubs."""

from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from app.contracts.chapters import ChapterCreate, ChapterRead, ChapterUpdate

router = APIRouter(prefix="/api/v1/chapters")


@router.post("", response_model=ChapterRead, status_code=HTTPStatus.CREATED)
def create_chapter(chapter: ChapterCreate) -> ChapterRead:
    raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)


@router.get("", response_model=list[ChapterRead])
def list_chapters() -> list[ChapterRead]:
    raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)


@router.get("/{chapter_id}", response_model=ChapterRead)
def get_chapter(chapter_id: int) -> ChapterRead:
    raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)


@router.patch("/{chapter_id}", response_model=ChapterRead)
def update_chapter(chapter_id: int, chapter: ChapterUpdate) -> ChapterRead:
    raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)


@router.post("/{chapter_id}/archive", response_model=ChapterRead)
def archive_chapter(chapter_id: int) -> ChapterRead:
    raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)
