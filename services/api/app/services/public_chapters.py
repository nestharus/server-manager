from __future__ import annotations

from app.contracts.public_chapters import (
    PublicChapterListRead,
    PublicChapterSummaryRead,
)
from app.repositories.db import PostgresDatabase
from app.repositories.public_chapters import list_public_active_chapters as list_public_active_chapter_rows


def list_public_chapters(db: PostgresDatabase) -> PublicChapterListRead:
    with db.connection() as connection:
        rows = list_public_active_chapter_rows(connection)
    return PublicChapterListRead(
        chapters=[PublicChapterSummaryRead.model_validate(row) for row in rows],
    )


# Service-layer alias mirrors the repository naming used by chapter-scoped callers.
list_public_active_chapters = list_public_chapters


__all__ = ["list_public_active_chapters", "list_public_chapters"]
