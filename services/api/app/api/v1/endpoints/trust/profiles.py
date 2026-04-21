"""Trust profile endpoints."""

from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.contracts.actor import ActorIdentity
from app.contracts.trust import TrustProfileRead, TrustSignalsInput
from app.core.dependencies import RequireAuthority, get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.trust import (
    compute_trust as compute_trust_service,
    get_trust_profile as get_trust_profile_service,
)

from ._shared import get_db, raise_for_trust_error, set_etag


router = APIRouter(prefix="/api/v1/trust")


@router.post(
    "/compute/{member_id}",
    response_model=TrustProfileRead,
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(RequireAuthority("trust.write", "global"))],
)
def compute_trust(
    member_id: UUID,
    signals: TrustSignalsInput,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> TrustProfileRead:
    try:
        read, result, created = compute_trust_service(db, member_id, signals, actor)
    except Exception as error:
        raise_for_trust_error(error)

    if not created:
        response.status_code = HTTPStatus.OK
    set_etag(response, result.etag if result is not None else f'"{read.version}"')
    return read


@router.get(
    "/{member_id}",
    response_model=TrustProfileRead,
    dependencies=[Depends(RequireAuthority("trust.read", "global"))],
)
def get_trust_profile(
    member_id: UUID,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
) -> TrustProfileRead:
    try:
        read, etag = get_trust_profile_service(db, member_id)
    except Exception as error:
        raise_for_trust_error(error)
    set_etag(response, etag)
    return read

