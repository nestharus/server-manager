from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.contracts.actor import ActorIdentity
from app.contracts.trust import TrustProfileRead
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.trust import recompute_trust_profile

from ._shared import get_db, raise_for_trust_error, require_authority, set_etag


router = APIRouter(prefix="/api/v1/trust/recompute")


@router.post(
    "/{member_id}",
    response_model=TrustProfileRead,
    status_code=HTTPStatus.OK,
)
def recompute_trust(
    member_id: UUID,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> TrustProfileRead:
    require_authority(
        db=db,
        actor=actor,
        permission="trust.recompute",
        scope_kind="member",
        scope_id=str(member_id),
    )
    try:
        read, result = recompute_trust_profile(db, member_id, actor)
    except Exception as error:
        raise_for_trust_error(error)
    set_etag(response, result.etag)
    return read

