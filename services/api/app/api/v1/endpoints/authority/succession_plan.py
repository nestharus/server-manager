from __future__ import annotations

from fastapi import APIRouter, Depends

from app.contracts.actor import ActorIdentity
from app.contracts.authority import SuccessionPlanRead
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.authority import compute_succession_plan

from ._shared import get_db, raise_known_authority_error


router = APIRouter(prefix="/api/v1/chapters")


@router.get("/{chapter_id}/succession-plan", response_model=SuccessionPlanRead)
def get_succession_plan_endpoint(
    chapter_id: str,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> SuccessionPlanRead:
    try:
        return compute_succession_plan(db, chapter_id=chapter_id, actor=actor)
    except Exception as error:
        raise_known_authority_error(error)
