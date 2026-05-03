from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Response

from app.contracts.actor import ActorIdentity
from app.contracts.compliance import EvidenceSubmissionCreate, EvidenceSubmissionRead
from app.core.container import ApiContainer
from app.core.dependencies import get_current_actor
from app.services.compliance import ComplianceService

from ._shared import raise_known_compliance_error, set_etag


router = APIRouter(prefix="/api/v1/compliance/evidence")


@router.post("", response_model=EvidenceSubmissionRead, status_code=HTTPStatus.CREATED)
@inject
def submit_evidence_endpoint(
    body: EvidenceSubmissionCreate,
    response: Response,
    service: ComplianceService = Depends(Provide[ApiContainer.services.compliance]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> EvidenceSubmissionRead:
    try:
        read, result = service.submit_evidence(body, actor=actor)
    except Exception as error:
        raise_known_compliance_error(error)
    set_etag(response, result.etag)
    return read


@router.get("/{evidence_id}", response_model=EvidenceSubmissionRead)
@inject
def get_evidence_endpoint(
    evidence_id: UUID,
    response: Response,
    service: ComplianceService = Depends(Provide[ApiContainer.services.compliance]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> EvidenceSubmissionRead:
    try:
        read = service.get_evidence_submission(evidence_id=evidence_id, actor=actor)
    except Exception as error:
        raise_known_compliance_error(error)
    set_etag(response, f'"{read.version}"')
    return read
