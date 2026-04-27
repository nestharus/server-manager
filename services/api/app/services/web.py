from __future__ import annotations

from app.contracts.web import AdminChapterListRead, AdminChapterSummaryRead
from app.repositories.db import PostgresDatabase
from app.repositories.web import list_admin_chapters


def list_web_admin_chapters(db: PostgresDatabase) -> AdminChapterListRead:
    with db.connection() as connection:
        rows = list_admin_chapters(connection)
    return AdminChapterListRead(
        chapters=[AdminChapterSummaryRead.model_validate(row) for row in rows],
    )
