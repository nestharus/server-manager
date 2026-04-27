from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.v1.endpoints.me import get_pomerium_principal
from app.contracts.web import AdminChapterListRead, CurrentPrincipalRead
from app.repositories.db import PostgresDatabase
from app.services.web import list_web_admin_chapters


router = APIRouter(prefix="/api/v1/web")


def _db(request: Request) -> PostgresDatabase:
    return request.app.state.db


@router.get("/admin/chapters", response_model=AdminChapterListRead)
def admin_chapters(
    _principal: CurrentPrincipalRead = Depends(get_pomerium_principal),
    db: PostgresDatabase = Depends(_db),
) -> AdminChapterListRead:
    return list_web_admin_chapters(db)
