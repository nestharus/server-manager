from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.authority import AuthorityGrantRead, AuthorityGrantTransferRequest
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.authority import get_authority_grant, transfer_authority_grant

from ._shared import get_db, parse_if_match_strong, raise_known_authority_error, set_etag


router = APIRouter(prefix="/api/v1/authority-grants")


@router.post("/{grant_id}/transfer", response_model=AuthorityGrantRead)
def transfer_authority_grant_endpoint(
    grant_id: UUID,
    body: AuthorityGrantTransferRequest,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> AuthorityGrantRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, created = transfer_authority_grant(
            db,
            grant_id=grant_id,
            expected_version=expected_version,
            request=body,
            actor=actor,
        )
        _fresh, etag = get_authority_grant(db, grant_id=read.id)
    except Exception as error:
        raise_known_authority_error(error)
    response.status_code = HTTPStatus.CREATED if created else HTTPStatus.OK
    set_etag(response, etag)
    return read
