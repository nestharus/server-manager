from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.contracts.actor import ActorIdentity
from app.contracts.authority import HandoffResult, LeadershipHandoffRequest
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.leadership_handoff_tickets import execute_handoff

from ._shared import get_db, raise_known_authority_error


router = APIRouter(prefix="/api/v1/authority-grants")


@router.post("/{grant_id}/handoff/tickets", response_model=HandoffResult)
def handoff_tickets_endpoint(
    grant_id: UUID,
    body: LeadershipHandoffRequest,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> HandoffResult:
    try:
        return execute_handoff(db, grant_id=grant_id, request=body, actor=actor)
    except Exception as error:
        raise_known_authority_error(error)
