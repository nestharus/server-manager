from __future__ import annotations

from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.compliance_corrections import OfficerCorrectionRead, OfficerCorrectionRequest
from app.core.container import ApiContainer
from app.core.dependencies import get_current_actor
from app.services.compliance_corrections import ComplianceCorrectionsService

from ._shared import parse_if_match_strong, raise_known_compliance_error, set_etag


router = APIRouter(prefix="/api/v1/compliance/evidence")


@router.post("/{evidence_id}/correct", response_model=OfficerCorrectionRead)
@inject
def correct_evidence_endpoint(
    evidence_id: UUID,
    body: OfficerCorrectionRequest,
    request: Request,
    response: Response,
    service: ComplianceCorrectionsService = Depends(
        Provide[ApiContainer.services.compliance_corrections]
    ),
    actor: ActorIdentity = Depends(get_current_actor),
) -> OfficerCorrectionRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, result = service.correct_evidence(
            evidence_id,
            body,
            expected_version=expected_version,
            actor=actor,
        )
    except Exception as error:
        raise_known_compliance_error(error)
    set_etag(response, result.etag)
    return read
