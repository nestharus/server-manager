from __future__ import annotations

from app.contracts.web import AdminChapterListRead, AdminChapterSummaryRead
from app.repositories.web import WebRepository


class WebService:
    def __init__(self, web_repo: WebRepository, mutations_callable) -> None:
        self._web_repo = web_repo
        self._mutations_callable = mutations_callable

    def list_web_admin_chapters(self) -> AdminChapterListRead:
        rows = self._web_repo.list_admin_chapters()
        return AdminChapterListRead(
            chapters=[AdminChapterSummaryRead.model_validate(row) for row in rows],
        )
