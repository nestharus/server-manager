from __future__ import annotations

from fastapi import Request

from app.contracts.actor import ActorIdentity
from app.core.context import get_current_actor as _get_current_actor
from app.services.chapters import ChapterService


def get_chapter_service(request: Request) -> ChapterService:
    return request.app.state.chapter_service


def get_current_actor() -> ActorIdentity:
    """FastAPI dependency: resolve the current actor from CURRENT_ACTOR.

    ActorMiddleware populates CURRENT_ACTOR before any endpoint dependency
    runs, so this is just a thin facade around the context helper.
    """
    return _get_current_actor()
