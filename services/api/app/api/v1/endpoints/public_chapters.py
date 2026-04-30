from __future__ import annotations

from fastapi import APIRouter, Depends

from app.contracts.public_chapters import PublicChapterListRead
from app.repositories.db import PostgresDatabase
from app.services.public_chapters import list_public_chapters

from .applications._shared import get_db


router = APIRouter(prefix="/api/v1/public/chapters")


@router.get("", response_model=PublicChapterListRead)
def list_public_chapters_endpoint(
    db: PostgresDatabase = Depends(get_db),
) -> PublicChapterListRead:
    """Public, no auth — returns active chapters only. No identity headers consumed."""
    return list_public_chapters(db)


__all__ = ["router"]
