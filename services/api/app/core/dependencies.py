from __future__ import annotations

from fastapi import Request

from app.services.chapters import ChapterService


def get_chapter_service(request: Request) -> ChapterService:
    return request.app.state.chapter_service
