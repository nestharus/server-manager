from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter, Depends, Response

from app.contracts.actor import ActorIdentity
from app.contracts.trust import TrustSignalCreate, TrustSignalRead
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.trust import create_trust_signal

from ._shared import get_db, raise_for_trust_error, require_authority, set_etag


router = APIRouter(prefix="/api/v1/trust/signals")


@router.post("", response_model=TrustSignalRead, status_code=HTTPStatus.CREATED)
def create_signal(
    body: TrustSignalCreate,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> TrustSignalRead:
    require_authority(
        db=db,
        actor=actor,
        permission="trust.signal.create",
        scope_kind=body.scope.scope_kind,
        scope_id=body.scope.scope_id,
    )
    try:
        read, result = create_trust_signal(db, body, actor)
    except Exception as error:
        raise_for_trust_error(error)
    set_etag(response, result.etag)
    return read
