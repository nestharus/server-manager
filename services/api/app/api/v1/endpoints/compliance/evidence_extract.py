from __future__ import annotations

from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Response

from app.contracts.actor import ActorIdentity
from app.contracts.compliance_extraction import EvidenceExtractionRead
from app.core.container import ApiContainer
from app.core.dependencies import get_current_actor
from app.services.compliance_extraction import ComplianceExtractionService

from ._shared import raise_known_compliance_error, set_etag


router = APIRouter(prefix="/api/v1/compliance/evidence")


@router.post("/{evidence_id}/extract", response_model=EvidenceExtractionRead)
@inject
def extract_evidence_endpoint(
    evidence_id: UUID,
    response: Response,
    service: ComplianceExtractionService = Depends(
        Provide[ApiContainer.services.compliance_extraction]
    ),
    actor: ActorIdentity = Depends(get_current_actor),
) -> EvidenceExtractionRead:
    try:
        read, result = service.trigger_extraction(evidence_id, actor=actor)
    except Exception as error:
        raise_known_compliance_error(error)
    set_etag(response, result.etag)
    return read
