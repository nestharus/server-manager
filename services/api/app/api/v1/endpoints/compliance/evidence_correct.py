from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.compliance_corrections import OfficerCorrectionRead, OfficerCorrectionRequest
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.compliance_corrections import correct_evidence

from ._shared import get_db, parse_if_match_strong, raise_known_compliance_error, set_etag


router = APIRouter(prefix="/api/v1/compliance/evidence")


@router.post("/{evidence_id}/correct", response_model=OfficerCorrectionRead)
def correct_evidence_endpoint(
    evidence_id: UUID,
    body: OfficerCorrectionRequest,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> OfficerCorrectionRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, result = correct_evidence(
            db,
            evidence_id,
            body,
            expected_version=expected_version,
            actor=actor,
        )
    except Exception as error:
        raise_known_compliance_error(error)
    set_etag(response, result.etag)
    return read
