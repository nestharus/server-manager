"""Chapter endpoints.

CRUD for chapters. All mutations are audited. Updates use optimistic
locking via the version field.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.contracts.chapters import (
    ChapterCreate,
    ChapterListResponse,
    ChapterResponse,
    ChapterUpdate,
)
from app.core.dependencies import get_chapter_service
from app.services.chapter_service import (
    ChapterArchivedError,
    ChapterNotFoundError,
    ChapterService,
    ChapterVersionConflictError,
    DuplicateChapterSlugError,
)

router = APIRouter(prefix="/chapters", tags=["chapters"])


@router.post("/", response_model=ChapterResponse, status_code=201)
async def create_chapter(
    body: ChapterCreate,
    service: ChapterService = Depends(get_chapter_service),
) -> ChapterResponse:
    """Create a new chapter.

    The chapter is created in the database. Discord roles, channels,
    and panels are provisioned separately via the provisioning subsystem.
    """
    try:
        return await service.create_chapter(body)
    except DuplicateChapterSlugError as exc:
        raise HTTPException(status_code=409, detail="Chapter slug already exists") from exc


@router.get("/", response_model=ChapterListResponse)
async def list_chapters(
    include_archived: bool = False,
    service: ChapterService = Depends(get_chapter_service),
) -> ChapterListResponse:
    """List all chapters, optionally including archived ones."""
    items = await service.list_chapters(include_archived=include_archived)
    return ChapterListResponse(items=items, total=len(items))


@router.get("/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(
    chapter_id: UUID,
    service: ChapterService = Depends(get_chapter_service),
) -> ChapterResponse:
    """Get a single chapter by ID."""
    try:
        return await service.get_chapter(chapter_id)
    except ChapterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chapter not found") from exc


@router.patch("/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(
    chapter_id: UUID,
    body: ChapterUpdate,
    service: ChapterService = Depends(get_chapter_service),
) -> ChapterResponse:
    """Update a chapter. Requires current version for optimistic locking.

    If the version doesn't match the current DB row, returns 409 Conflict.
    """
    try:
        return await service.update_chapter(chapter_id, body)
    except ChapterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chapter not found") from exc
    except ChapterArchivedError as exc:
        raise HTTPException(status_code=409, detail="Chapter is archived") from exc
    except ChapterVersionConflictError as exc:
        raise HTTPException(status_code=409, detail="Chapter version conflict") from exc


@router.post("/{chapter_id}/archive", response_model=ChapterResponse)
async def archive_chapter(
    chapter_id: UUID,
    service: ChapterService = Depends(get_chapter_service),
) -> ChapterResponse:
    """Soft-delete a chapter by setting archived_at."""
    try:
        return await service.archive_chapter(chapter_id)
    except ChapterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chapter not found") from exc
    except ChapterArchivedError as exc:
        raise HTTPException(status_code=409, detail="Chapter already archived") from exc
