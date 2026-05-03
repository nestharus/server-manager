from __future__ import annotations

from app.contracts.public_chapters import (
    PublicChapterListRead,
    PublicChapterSummaryRead,
)
from app.repositories.public_chapters import PublicChaptersRepository


class PublicChaptersService:
    def __init__(self, public_chapters_repo: PublicChaptersRepository) -> None:
        self._public_chapters_repo = public_chapters_repo

    def list_public_chapters(self) -> PublicChapterListRead:
        rows = self._public_chapters_repo.list_public_active_chapters()
        return PublicChapterListRead(
            chapters=[PublicChapterSummaryRead.model_validate(row) for row in rows],
        )


__all__ = ["PublicChaptersService"]
