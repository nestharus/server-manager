from __future__ import annotations

from datetime import UTC, datetime

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.contracts.actor import ActorIdentity
from app.contracts.read_models import LeadershipContextRead
from app.core.container import ApiContainer
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.read_models import read_leadership_context

from ._shared import raise_known_authority_error


router = APIRouter(prefix="/api/v1/members")


@router.get("/{member_id}/leadership-context", response_model=LeadershipContextRead)
@inject
def get_leadership_context_endpoint(
    member_id: str,
    db: PostgresDatabase = Depends(Provide[ApiContainer.core.db]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> LeadershipContextRead:
    try:
        return read_leadership_context(
            db,
            member_id=member_id,
            actor=actor,
            now=datetime.now(UTC),
        )
    except Exception as error:
        raise_known_authority_error(error)
